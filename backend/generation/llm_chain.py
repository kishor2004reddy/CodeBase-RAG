"""
generation/llm_chain.py
-----------------------
LangChain-based LLM generation chain using ChatGroq.

Uses:
  - ChatGroq         — LangChain wrapper around Groq API
  - ChatPromptTemplate + MessagesPlaceholder — structured prompt with injected chat history
  - BaseMessage types (HumanMessage, AIMessage) — native LangGraph message format

History injection is handled automatically via MessagesPlaceholder, which reads
`state["messages"]` from the LangGraph state — no manual list building required.

Strict answer rules are preserved:
  - Grounded ONLY on provided codebase context
  - Mandatory file citations [filepath#Lstart-Lend]
  - Falls back gracefully if context is insufficient
"""

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from retrieval.hybrid_retriever import RetrievedContext

logger = get_logger(__name__)


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are CodeGraphRAG, an expert AI assistant specializing in deep codebase reasoning over multi-language repositories.

Your task is to answer the user's question about the codebase strictly and accurately based ONLY on the provided context (which includes vector search code snippets, symbol definitions, and Neo4j graph dependency structures).

STRICT RULES YOU MUST FOLLOW:
1. Grounding: Rely ONLY on the facts given in the context. Do NOT invent, assume, or extrapolate details not present in the context.
2. Fallback: If the context does not contain enough information to answer the question, state clearly: "Based on the indexed codebase context, I cannot find enough details to answer this question."
3. Mandatory Citations: Every time you reference a function, class, file, or architectural component, you MUST include a precise file citation in the format `[filepath#Lstart-Lend]` (e.g. `[backend/main.py#L18-L46]`).
4. Structure & Quality: Provide clear, concise Markdown explanations, referencing call chains and dependencies where relevant. Use code blocks for snippets.
"""


# ── Response model ────────────────────────────────────────────────────────────

class QueryAnswer(BaseModel):
    """Response object returned to the API layer."""

    answer: str
    citations: list[str] = Field(default_factory=list)
    model_used: str
    context_chunks_count: int


# ── Chain builder ─────────────────────────────────────────────────────────────

def build_llm_chain(use_code_model: bool = False) -> tuple[Runnable, str]:
    """
    Build and return a LangChain runnable chain for RAG answer generation.

    The chain structure is:
        ChatPromptTemplate (system + history + current question) | ChatGroq

    MessagesPlaceholder("messages") automatically injects the full conversation
    history from the LangGraph state, enabling multi-turn memory with zero
    manual list management.

    Parameters
    ----------
    use_code_model : bool
        If True, uses the DeepSeek code-specialised model. Otherwise uses
        the general LLaMA model.

    Returns
    -------
    tuple[Runnable, str]
        (compiled chain, model name used)
    """
    model_name = (
        settings.groq_model_code if use_code_model else settings.groq_model_general
    )

    llm = ChatGroq(
        model=model_name,
        api_key=settings.groq_api_key,
        temperature=0.2,    # Low temperature for factual, grounded answers
        max_tokens=1500,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        # Injects state["messages"] — full prior conversation history
        MessagesPlaceholder(variable_name="messages"),
        # Current user question with retrieval context appended
        ("human", "{user_message}"),
    ])

    chain = prompt | llm
    return chain, model_name


# ── Message builder ───────────────────────────────────────────────────────────

def build_user_message(query: str, context: RetrievedContext) -> str:
    """
    Format the current user question with retrieval context into a single
    human message string. This is passed as `user_message` to the chain.

    The retrieval context (vector hits, symbol graph, Cypher expansion) is
    appended directly to the question so the LLM has full grounding material.
    """
    return (
        f"USER QUESTION:\n{query}\n\n"
        f"CONTEXT FROM CODEBASE (Vector Search + Symbol Graph + Dependency Traversal):\n"
        f"{context.formatted_context_str}\n\n"
        f"Please answer the question accurately using the context above. "
        f"Include mandatory file citations [filepath#Lstart-Lend]."
    )
