"""
generation/llm_chain.py
-----------------------
LLM answer generation chain using Groq API.

Applies strict prompt constraints:
  - Answers based ONLY on the provided codebase context.
  - Requires mandatory file citations in [filepath#Lstart-Lend] format.
  - Falls back to "Not found in indexed repository" if information is missing.
"""

from groq import Groq
from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from retrieval.hybrid_retriever import RetrievedContext

logger = get_logger(__name__)

_groq_client: Groq | None = None


def _get_groq_client() -> Groq:
    """Singleton Groq client."""
    global _groq_client
    if _groq_client is None:
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not configured in .env file. Please add your key."
            )
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


SYSTEM_PROMPT = """You are CodeGraphRAG, an expert AI assistant specializing in deep codebase reasoning over multi-language repositories.

Your task is to answer the user's question about the codebase strictly and accurately based ONLY on the provided context (which includes vector search code snippets, symbol definitions, and Neo4j graph dependency structures).

STRICT RULES YOU MUST FOLLOW:
1. Grounding: Rely ONLY on the facts given in the context. Do NOT invent, assume, or extrapolate details not present in the context.
2. Fallback: If the context does not contain enough information to answer the question, state clearly: "Based on the indexed codebase context, I cannot find enough details to answer this question."
3. Mandatory Citations: Every time you reference a function, class, file, or architectural component, you MUST include a precise file citation in the format `[filepath#Lstart-Lend]` (e.g. `[backend/main.py#L18-L46]`).
4. Structure & Quality: Provide clear, concise Markdown explanations, referencing call chains and dependencies where relevant. Use code blocks for snippets.
"""


class QueryAnswer(BaseModel):
    """Response object returned to the user."""

    answer: str
    citations: list[str] = Field(default_factory=list)
    model_used: str
    context_chunks_count: int


def generate_answer(
    query: str,
    context: RetrievedContext,
    use_code_model: bool = False,
) -> QueryAnswer:
    """
    Generate an answer to user query given retrieved context using Groq LLM.

    Parameters
    ----------
    query : str
        User natural language question.
    context : RetrievedContext
        Hybrid context from retriever.
    use_code_model : bool
        Whether to use deepseek code model or general llama model.

    Returns
    -------
    QueryAnswer
        Answer text + structured citations.
    """
    client = _get_groq_client()
    model_name = settings.groq_model_code if use_code_model else settings.groq_model_general

    user_message = f"""USER QUESTION:
{query}

CONTEXT FROM CODEBASE (Vector Search + Symbol Graph + Dependency Traversal):
{context.formatted_context_str}

Please answer the question accurately using the context above. Include mandatory file citations [filepath#Lstart-Lend].
"""

    logger.info("Generating answer via Groq model: %s", model_name)

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,   # Low temperature for factual grounding
            max_tokens=1500,
        )

        answer_text = completion.choices[0].message.content or ""

        return QueryAnswer(
            answer=answer_text,
            citations=context.file_citations,
            model_used=model_name,
            context_chunks_count=len(context.vector_results) + len(context.symbol_results),
        )

    except Exception as e:
        logger.error("LLM generation failed: %s", e, exc_info=True)
        raise RuntimeError(f"LLM generation failed: {e}") from e
