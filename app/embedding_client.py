"""Gemini Embedding 2 client for document and query embedding.

Wraps the Google Generative AI SDK to produce 768-dimensional embeddings
using task-instruction prefixes baked into the input text (gemini-embedding-2
does not support a task_type parameter like its predecessor).
"""

import asyncio
import time
import logging

from google import genai

from app.database import settings

logger = logging.getLogger(__name__)

MODEL = "gemini-embedding-2"
OUTPUT_DIMENSIONALITY = 768

DOCUMENT_PREFIX = "Represent this product for retrieval: "
QUERY_PREFIX = "Represent this search query for retrieving relevant products: "

MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0

# Lazy-initialized client (created on first use to avoid import-time side effects
# when GOOGLE_AI_API_KEY is not set, e.g. during v1/v2-only usage or testing)
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the Gemini API client."""
    global _client
    if _client is None:
        api_key = getattr(settings, "GOOGLE_AI_API_KEY", None)
        if not api_key:
            raise RuntimeError(
                "GOOGLE_AI_API_KEY is not set. "
                "Add it to your .env file to use embedding features."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _embed_sync(text_input: str, prefix: str) -> list[float]:
    """Synchronous embedding call with retry logic.

    Prepends the appropriate task-instruction prefix to the input text
    and calls gemini-embedding-2 with output_dimensionality=768.
    """
    client = _get_client()
    prefixed_text = f"{prefix}{text_input}"

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            result = client.models.embed_content(
                model=MODEL,
                contents=prefixed_text,
                config={
                    "output_dimensionality": OUTPUT_DIMENSIONALITY,
                },
            )
            return list(result.embeddings[0].values)
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY_SECONDS * (2 ** attempt)
                logger.warning(
                    "Embedding attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)

    raise RuntimeError(
        f"Embedding failed after {MAX_RETRIES} attempts: {last_error}"
    ) from last_error


def _embed_batch_sync(texts: list[str], prefix: str) -> list[list[float]]:
    """Synchronous batch embedding call with retry logic.

    Embeds multiple texts in a single API call. Each text gets the
    task-instruction prefix prepended internally.
    """
    client = _get_client()
    prefixed_texts = [f"{prefix}{t}" for t in texts]

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            result = client.models.embed_content(
                model=MODEL,
                contents=prefixed_texts,
                config={
                    "output_dimensionality": OUTPUT_DIMENSIONALITY,
                },
            )
            return [list(e.values) for e in result.embeddings]
        except Exception as exc:
            last_error = exc
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY_SECONDS * (2 ** attempt)
                logger.warning(
                    "Batch embedding attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)

    raise RuntimeError(
        f"Batch embedding failed after {MAX_RETRIES} attempts: {last_error}"
    ) from last_error


async def embed_document(text_input: str) -> list[float]:
    """Embed a product document string.

    Prepends the document task instruction prefix:
    "Represent this product for retrieval: "

    Returns a 768-dimensional float vector.
    """
    return await asyncio.to_thread(_embed_sync, text_input, DOCUMENT_PREFIX)


async def embed_query(text_input: str) -> list[float]:
    """Embed a search query string.

    Prepends the query task instruction prefix:
    "Represent this search query for retrieving relevant products: "

    Returns a 768-dimensional float vector.
    """
    return await asyncio.to_thread(_embed_sync, text_input, QUERY_PREFIX)


async def embed_documents_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple product document strings in a single API call.

    Prepends the document task instruction prefix to each text.

    Returns a list of 768-dimensional float vectors, one per input text.
    """
    return await asyncio.to_thread(_embed_batch_sync, texts, DOCUMENT_PREFIX)
