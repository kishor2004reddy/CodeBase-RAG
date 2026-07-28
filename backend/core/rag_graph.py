"""
core/rag_graph.py
-----------------
LangGraph StateGraph for CodeGraphRAG — persistent multi-turn chat with time-travel.

Graph topology:
    START → [retrieve_node] → [generate_node] → END

State is checkpointed to Redis after every invocation via RedisSaver.
Each session is identified by a `thread_id` (= session_id from the API).

Features:
  - Persistent memory:  history survives server restarts via Redis
  - Multi-session:      each thread_id is fully isolated
  - Time-travel:        graph.get_state_history() + graph.update_state() for rollback
  - Auto-TTL:           inactive sessions expire after settings.session_ttl_minutes
"""

from __future__ import annotations

import redis as redis_lib
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.redis import RedisSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from core.config import settings
from core.logging import get_logger
from generation.llm_chain import QueryAnswer, build_llm_chain, build_user_message
from retrieval.hybrid_retriever import RetrievedContext, retrieve_context

logger = get_logger(__name__)

# ── Singleton graph instance ──────────────────────────────────────────────────

_compiled_graph = None


# ── State definition ──────────────────────────────────────────────────────────


class RAGState(TypedDict):
    """
    Shared state for the RAG graph.

    `messages` uses the `add_messages` reducer — LangGraph automatically
    APPENDS new messages to the list rather than overwriting it. This is
    how conversation history accumulates across turns.
    """

    # Conversation history — persisted as LangChain BaseMessage objects
    messages: Annotated[list[BaseMessage], add_messages]

    # Per-invocation inputs (fresh each call)
    query: str
    repo_id: str
    use_code_model: bool

    # Retrieval output — passed from retrieve_node to generate_node
    retrieved: RetrievedContext | None

    # Response metadata — populated by generate_node
    citations: list[str]
    model_used: str
    context_chunks_count: int


# ── Graph nodes ───────────────────────────────────────────────────────────────


def retrieve_node(state: RAGState) -> dict:
    """
    Retrieval node — runs the hybrid retriever (Qdrant + Neo4j).

    Calls the existing `retrieve_context()` function unchanged.
    Stores the result in state["retrieved"] for the generate node.
    """
    logger.info("retrieve_node: querying repo=%s q='%s'", state["repo_id"], state["query"])

    retrieved = retrieve_context(
        query=state["query"],
        repo_id=state["repo_id"],
    )

    return {"retrieved": retrieved}


def generate_node(state: RAGState) -> dict:
    """
    Generation node — calls ChatGroq via LangChain chain with full history.

    MessagesPlaceholder in the prompt template automatically injects
    state["messages"] (all prior turns) so the LLM has full context.

    After generation, both the current HumanMessage and the AIMessage
    response are appended to state["messages"] via the add_messages reducer.
    """
    logger.info("generate_node: generating answer for q='%s'", state["query"])

    retrieved: RetrievedContext = state["retrieved"]
    chain, model_name = build_llm_chain(use_code_model=state.get("use_code_model", False))

    # Build the current user message (question + retrieval context)
    user_message_text = build_user_message(state["query"], retrieved)

    # Cap history to avoid token overflow — most recent turns take priority
    max_msgs = settings.max_history_turns * 2   # each turn = 1 Human + 1 AI message
    history = list(state.get("messages", []))[-max_msgs:]

    # Invoke the LangChain chain
    # chain = ChatPromptTemplate(system + MessagesPlaceholder + human) | ChatGroq
    ai_response = chain.invoke({
        "messages": history,
        "user_message": user_message_text,
    })

    answer_text: str = ai_response.content or ""

    # Return new messages to append — add_messages reducer handles the merge
    return {
        "messages": [
            HumanMessage(content=user_message_text),  # current question + context
            AIMessage(content=answer_text),            # model answer
        ],
        "citations": retrieved.file_citations,
        "model_used": model_name,
        "context_chunks_count": (
            len(retrieved.vector_results) + len(retrieved.symbol_results)
        ),
    }


# ── Graph builder ─────────────────────────────────────────────────────────────


def build_rag_graph(checkpointer: RedisSaver):
    """Assemble and compile the StateGraph with the given checkpointer."""
    builder = StateGraph(RAGState)

    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)

    return builder.compile(checkpointer=checkpointer)


# ── Singleton initialiser ─────────────────────────────────────────────────────


def init_rag_graph() -> None:
    """
    Initialise the RedisSaver and compile the graph.

    Must be called once during app startup (in lifespan).
    Stores the compiled graph in the module-level singleton.

    NOTE: RedisSaver.from_conn_string() returns a context manager, not a
    saver instance — calling .setup() on it fails. We pass a direct Redis
    client to the RedisSaver constructor instead.
    """
    global _compiled_graph

    logger.info("Initialising LangGraph RAG graph with RedisSaver...")

    ttl_config = {
        "default_ttl": settings.session_ttl_minutes * 60,  # convert to seconds
        "refresh_on_read": True,                           # reset TTL on access
    }

    # Create a raw Redis client and pass it directly to RedisSaver.
    # from_conn_string() returns a _GeneratorContextManager, not a RedisSaver.
    redis_client = redis_lib.from_url(settings.redis_url)
    checkpointer = RedisSaver(redis_client=redis_client, ttl=ttl_config)
    checkpointer.setup()   # creates required Redis indices (idempotent)

    _compiled_graph = build_rag_graph(checkpointer)
    logger.info("LangGraph RAG graph ready.")


def get_rag_graph():
    """
    Return the singleton compiled graph.

    Raises RuntimeError if `init_rag_graph()` has not been called yet.
    """
    if _compiled_graph is None:
        raise RuntimeError(
            "RAG graph has not been initialised. "
            "Call init_rag_graph() during app startup."
        )
    return _compiled_graph
