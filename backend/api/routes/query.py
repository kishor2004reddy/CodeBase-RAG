"""
api/routes/query.py
-------------------
REST API endpoints for querying an ingested codebase with persistent chat memory.

Endpoints:
  POST   /api/query                                   — submit query, get grounded answer
  GET    /api/session/{session_id}/history            — list all checkpoints for a session
  POST   /api/session/{session_id}/rollback/{chk_id} — roll back to a prior checkpoint
  DELETE /api/session/{session_id}                    — wipe session from Redis
"""

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.logging import get_logger
from core.rag_graph import get_rag_graph

logger = get_logger(__name__)

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────


class QueryRequest(BaseModel):
    """Request body for submitting codebase queries."""

    query: str = Field(..., description="Natural language question about the codebase")
    repo_id: str = Field(..., description="Target repository identifier")
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation continuity. A new UUID is generated if not provided.",
    )
    use_code_model: bool = Field(
        default=False,
        description="Use DeepSeek-Coder LLM model if True, otherwise LLaMA general model.",
    )


class QueryResponse(BaseModel):
    """API response containing answer, citations, and session metadata."""

    query: str
    repo_id: str
    session_id: str           # always returned so the frontend can track the thread
    checkpoint_id: str        # LangGraph checkpoint ID — use this for rollback
    answer: str
    citations: list[str]
    model_used: str
    graph_nodes_count: int
    context_chunks_count: int


class CheckpointInfo(BaseModel):
    """Metadata for a single conversation checkpoint."""

    checkpoint_id: str
    turn_index: int
    timestamp: str | None
    query_preview: str        # first 120 chars of the user query at this turn


class SessionHistoryResponse(BaseModel):
    """List of all checkpoints for a session."""

    session_id: str
    total_turns: int
    checkpoints: list[CheckpointInfo]


# ── POST /api/query ───────────────────────────────────────────────────────────


@router.post("/query", response_model=QueryResponse)
async def query_codebase(request: QueryRequest):
    """
    Query an ingested codebase using hybrid retrieval, LangChain generation,
    and LangGraph-managed persistent session memory.

    If `session_id` is not provided, a new UUID session is created automatically.
    The returned `checkpoint_id` can be used later to roll back to this exact turn.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
    if not request.repo_id.strip():
        raise HTTPException(status_code=400, detail="repo_id must be provided.")

    # Generate a new session ID if not provided
    session_id = request.session_id or str(uuid4())
    config = {"configurable": {"thread_id": session_id}}

    logger.info(
        "Query received — session=%s repo=%s query='%s'",
        session_id, request.repo_id, request.query,
    )

    try:
        graph = get_rag_graph()

        # Invoke the graph — LangGraph loads history from Redis, runs retrieve →
        # generate, then checkpoints the new state back to Redis automatically.
        result = graph.invoke(
            {
                "query": request.query,
                "repo_id": request.repo_id,
                "use_code_model": request.use_code_model,
                "retrieved": None,
                "citations": [],
                "model_used": "",
                "context_chunks_count": 0,
            },
            config=config,
        )

        # Get the checkpoint ID of the state just saved
        current_state = graph.get_state(config)
        checkpoint_id = current_state.config["configurable"].get("checkpoint_id", "")

        # Extract the AI answer from the last message in state
        messages = result.get("messages", [])
        answer_text = ""
        if messages:
            answer_text = messages[-1].content if hasattr(messages[-1], "content") else ""

        return QueryResponse(
            query=request.query,
            repo_id=request.repo_id,
            session_id=session_id,
            checkpoint_id=checkpoint_id,
            answer=answer_text,
            citations=result.get("citations", []),
            model_used=result.get("model_used", ""),
            graph_nodes_count=len(result.get("messages", [])) // 2,
            context_chunks_count=result.get("context_chunks_count", 0),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Query execution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


# ── GET /api/session/{session_id}/history ─────────────────────────────────────


@router.get("/session/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str):
    """
    Return all checkpoints for a session in chronological order.

    Each checkpoint includes:
      - checkpoint_id  — use this to roll back to a specific turn
      - turn_index     — sequential turn number (0-based)
      - timestamp      — when this turn was created
      - query_preview  — first 120 chars of the user question at this checkpoint
    """
    try:
        graph = get_rag_graph()
        config = {"configurable": {"thread_id": session_id}}

        # get_state_history returns most-recent-first — we reverse to chronological
        history_states = list(graph.get_state_history(config))
        history_states.reverse()

        checkpoints: list[CheckpointInfo] = []
        for idx, state_snapshot in enumerate(history_states):
            chk_id = state_snapshot.config["configurable"].get("checkpoint_id", "")

            # Extract user query preview from the HumanMessage at this turn
            query_preview = ""
            msgs = state_snapshot.values.get("messages", [])
            # Human messages are at even indices (0, 2, 4...)
            human_msgs = [m for m in msgs if hasattr(m, "type") and m.type == "human"]
            if human_msgs:
                raw_content = human_msgs[-1].content or ""
                # Strip the retrieval context block — show only the question part
                question_line = raw_content.split("\n\nCONTEXT FROM CODEBASE")[0]
                question_line = question_line.replace("USER QUESTION:\n", "")
                query_preview = question_line[:120]

            ts = None
            if state_snapshot.created_at:
                ts = str(state_snapshot.created_at)

            checkpoints.append(CheckpointInfo(
                checkpoint_id=chk_id,
                turn_index=idx,
                timestamp=ts,
                query_preview=query_preview,
            ))

        return SessionHistoryResponse(
            session_id=session_id,
            total_turns=len(checkpoints),
            checkpoints=checkpoints,
        )

    except Exception as e:
        logger.error("Failed to fetch session history for %s: %s", session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch session history: {e}")


# ── POST /api/session/{session_id}/rollback/{checkpoint_id} ───────────────────


@router.post("/session/{session_id}/rollback/{checkpoint_id}")
async def rollback_session(session_id: str, checkpoint_id: str):
    """
    Roll back a session to a specific checkpoint.

    After rollback, the next query on this session_id will resume from
    the rolled-back state — future turns after that checkpoint are discarded.

    Use `GET /api/session/{session_id}/history` to find checkpoint_ids.
    """
    try:
        graph = get_rag_graph()

        # The target config points to the specific checkpoint we want to restore
        target_config = {
            "configurable": {
                "thread_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        }

        # Load the target snapshot
        target_state = graph.get_state(target_config)
        if not target_state or not target_state.values:
            raise HTTPException(
                status_code=404,
                detail=f"Checkpoint '{checkpoint_id}' not found for session '{session_id}'.",
            )

        # Update the graph state to the target checkpoint —
        # this sets the head of the session to this point.
        # The `as_node` parameter tells LangGraph this update comes from
        # after the last node, so next invocation starts fresh from this state.
        current_config = {"configurable": {"thread_id": session_id}}
        graph.update_state(
            current_config,
            target_state.values,
            as_node="generate",
        )

        logger.info(
            "Session %s rolled back to checkpoint %s", session_id, checkpoint_id
        )

        return {
            "session_id": session_id,
            "rolled_back_to": checkpoint_id,
            "message": "Session rolled back successfully. Next query will resume from this checkpoint.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Rollback failed for session %s: %s", session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Rollback failed: {e}")


# ── DELETE /api/session/{session_id} ─────────────────────────────────────────


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Permanently delete all checkpoints for a session from Redis.

    This is irreversible — the entire conversation history is wiped.
    """
    try:
        graph = get_rag_graph()
        checkpointer = graph.checkpointer

        # Delete all checkpoint data for this thread from Redis
        checkpointer.adelete_thread(session_id) if hasattr(checkpointer, "adelete_thread") \
            else _delete_thread_sync(checkpointer, session_id)

        logger.info("Session %s deleted from Redis.", session_id)
        return {
            "session_id": session_id,
            "message": "Session deleted successfully.",
        }

    except Exception as e:
        logger.error("Failed to delete session %s: %s", session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}")


def _delete_thread_sync(checkpointer, thread_id: str) -> None:
    """
    Synchronous thread deletion helper.

    LangGraph's RedisSaver exposes Redis directly — we delete all keys
    associated with the thread_id pattern.
    """
    try:
        # RedisSaver stores checkpoints under keys prefixed with the thread_id
        if hasattr(checkpointer, "conn"):
            redis_client = checkpointer.conn
            pattern = f"*{thread_id}*"
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
    except Exception as e:
        logger.warning("Could not delete Redis keys for thread %s: %s", thread_id, e)
