"""Batch embedding pipeline for product_master rows.

Selects all rows WHERE embedding IS NULL, builds the document text template,
calls Gemini Embedding 2 in batches of 100, and updates each row's embedding
column. Idempotent — safe to re-run; only processes unembedded rows.

Usage:
    .venv/Scripts/python.exe scripts/embed_products.py
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing app modules so GOOGLE_AI_API_KEY is available
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

# Ensure project root is in python path to support direct script execution
sys.path.insert(0, str(project_root))

from sqlalchemy import text as sa_text

from app.database import engine
from app.embedding_client import _embed_batch_sync, DOCUMENT_PREFIX

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 100


def build_document_text(row: dict) -> str:
    """Build the embedding document text from product fields.

    Template:
        {name}. Brand: {brand}. Category: {category} > {sub_category}. Type: {type}. Model: {model_number}.
    """
    name = row.get("name") or ""
    brand = row.get("brand") or ""
    category = row.get("category") or ""
    sub_category = row.get("sub_category") or ""
    product_type = row.get("type") or ""
    model_number = row.get("model_number") or ""

    return (
        f"{name}. "
        f"Brand: {brand}. "
        f"Category: {category} > {sub_category}. "
        f"Type: {product_type}. "
        f"Model: {model_number}."
    )


async def count_unembedded() -> int:
    """Count rows with NULL embedding."""
    async with engine.connect() as conn:
        result = await conn.execute(
            sa_text("SELECT COUNT(*) FROM product_master WHERE embedding IS NULL")
        )
        return result.scalar_one()


async def fetch_batch(offset: int) -> list[dict]:
    """Fetch a batch of unembedded rows."""
    async with engine.connect() as conn:
        result = await conn.execute(
            sa_text(
                "SELECT id, name, brand, category, sub_category, type, model_number "
                "FROM product_master "
                "WHERE embedding IS NULL "
                "ORDER BY id "
                "LIMIT :limit OFFSET :offset"
            ),
            {"limit": BATCH_SIZE, "offset": offset},
        )
        return [dict(row) for row in result.mappings().all()]


async def update_embeddings(updates: list[dict]) -> None:
    """Update embedding column for a batch of rows."""
    async with engine.begin() as conn:
        for update in updates:
            await conn.execute(
                sa_text(
                    "UPDATE product_master SET embedding = :embedding WHERE id = :id"
                ),
                {"embedding": str(update["embedding"]), "id": update["id"]},
            )


async def main() -> None:
    total_unembedded = await count_unembedded()

    if total_unembedded == 0:
        logger.info("All rows already have embeddings. Nothing to do.")
        return

    total_batches = (total_unembedded + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(
        "Starting embedding pipeline: %d unembedded rows, ~%d batches of %d",
        total_unembedded,
        total_batches,
        BATCH_SIZE,
    )

    processed = 0
    batch_num = 0
    start_time = time.time()

    while True:
        # Always fetch from offset 0 because each successful batch removes rows
        # from the WHERE embedding IS NULL result set
        rows = await fetch_batch(offset=0)
        if not rows:
            break

        batch_num += 1
        texts = [build_document_text(row) for row in rows]

        # Call the synchronous batch embedding function directly
        # (we're in an async context but this is a script, not the web server)
        embeddings = await asyncio.to_thread(
            _embed_batch_sync, texts, DOCUMENT_PREFIX
        )

        # Prepare updates
        updates = []
        for row, embedding in zip(rows, embeddings):
            updates.append({"id": row["id"], "embedding": embedding})

        await update_embeddings(updates)

        processed += len(rows)
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0

        logger.info(
            "Batch %d/%d: embedded %d rows (%d/%d total, %.1f rows/sec)",
            batch_num,
            total_batches,
            len(rows),
            processed,
            total_unembedded,
            rate,
        )

    elapsed = time.time() - start_time
    logger.info(
        "Embedding pipeline complete: %d rows in %.1f seconds (%.1f rows/sec)",
        processed,
        elapsed,
        processed / elapsed if elapsed > 0 else 0,
    )

    # Verification
    remaining = await count_unembedded()
    logger.info("Remaining unembedded rows: %d", remaining)

    if remaining > 0:
        logger.warning(
            "Some rows still lack embeddings. Re-run this script to process them."
        )
    else:
        logger.info("All rows have embeddings. Pipeline fully complete.")


if __name__ == "__main__":
    asyncio.run(main())
