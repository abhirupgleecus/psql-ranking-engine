"""Bulk-seed embedding vectors from PostgreSQL into Elasticsearch.

Debezium cannot serialize PostgreSQL's vector(768) type, so embeddings are
never carried through the CDC pipeline.  This script bridges that gap by:

  1. Querying Cloud SQL for all (uuid, embedding) pairs where embedding IS NOT NULL.
  2. Issuing Elasticsearch bulk _update requests to inject the vector into the
     already-indexed documents (keyed by uuid which is the ES document _id).

Run this AFTER:
  - embed_products.py has populated the embedding column in PostgreSQL.
  - The CDC connector has fully replayed all product_master rows into ES.

The script is idempotent — re-running it will simply overwrite the embedding
field with the same value for already-seeded documents.

Usage:
    .venv/Scripts/python.exe scripts/seed_es_embeddings.py
    .venv/Scripts/python.exe scripts/seed_es_embeddings.py --batch-size 200
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from sqlalchemy import text as sa_text

from app.database import engine, settings
from app.elastic_client import create_async_elasticsearch_client, is_elastic_configured

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 500


async def count_embedded_pg() -> int:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa_text("SELECT COUNT(*) FROM product_master WHERE embedding IS NOT NULL")
        )
        return result.scalar_one()


async def fetch_pg_embeddings(offset: int, limit: int) -> list[dict]:
    """Fetch a batch of (uuid, embedding) rows from PostgreSQL."""
    async with engine.connect() as conn:
        result = await conn.execute(
            sa_text(
                "SELECT uuid, embedding::text FROM product_master "
                "WHERE embedding IS NOT NULL "
                "ORDER BY id "
                "LIMIT :limit OFFSET :offset"
            ),
            {"limit": limit, "offset": offset},
        )
        return [dict(row) for row in result.mappings().all()]


def _parse_pg_vector(raw: str) -> list[float]:
    """Parse a PostgreSQL vector literal '[0.1,0.2,...]' into a Python float list."""
    # pg returns the vector as a string like '[0.1,0.2,...]'
    return [float(x) for x in raw.strip("[]").split(",")]


async def build_uuid_to_es_id_map(client, index: str) -> dict[str, str]:
    """Scroll through all Elasticsearch documents to map uuid -> ES _id.

    Necessary because under key.ignore: true, the ES _id is coordinates
    (topic+partition+offset) rather than the product UUID.
    """
    logger.info("Building UUID-to-ES-ID mapping from Elasticsearch index...")
    uuid_to_es_id = {}

    resp = await client.search(
        index=index,
        scroll="2m",
        size=5000,
        _source=["uuid"]
    )
    scroll_id = resp.get("_scroll_id")
    hits = resp["hits"]["hits"]

    try:
        while hits:
            for hit in hits:
                uuid_str = hit["_source"].get("uuid")
                if uuid_str:
                    uuid_to_es_id[uuid_str] = hit["_id"]

            resp = await client.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp.get("_scroll_id")
            hits = resp["hits"]["hits"]
    finally:
        if scroll_id:
            await client.clear_scroll(scroll_id=scroll_id)

    logger.info("Mapping built: %d documents found in ES", len(uuid_to_es_id))
    return uuid_to_es_id


async def bulk_update_es(
    client,
    index: str,
    rows: list[dict],
    uuid_to_es_id: dict[str, str],
) -> tuple[int, int]:
    """Send a bulk _update request to inject embedding vectors.

    Returns (success_count, error_count).
    """
    operations = []
    skipped_count = 0
    for row in rows:
        uuid = str(row["uuid"])
        es_id = uuid_to_es_id.get(uuid)
        if not es_id:
            logger.warning("UUID %s not found in Elasticsearch index mapping", uuid)
            skipped_count += 1
            continue
        vector = _parse_pg_vector(row["embedding"])
        operations.append(json.dumps({"update": {"_index": index, "_id": es_id}}))
        operations.append(json.dumps({"doc": {"embedding": vector}, "doc_as_upsert": False}))

    if not operations:
        return 0, skipped_count

    body = "\n".join(operations) + "\n"
    resp = await client.bulk(body=body)

    errors = skipped_count
    for item in resp.get("items", []):
        op = item.get("update", {})
        if op.get("error"):
            logger.warning("ES update error for %s: %s", op.get("_id"), op["error"])
            errors += 1

    return len(rows) - errors, errors


async def main(batch_size: int) -> None:
    if not is_elastic_configured():
        logger.error(
            "Elasticsearch is not configured. Set ELASTIC_URL in .env."
        )
        sys.exit(1)

    total = await count_embedded_pg()
    if total == 0:
        logger.error(
            "No embedded rows found in PostgreSQL. "
            "Run scripts/embed_products.py first."
        )
        sys.exit(1)

    logger.info(
        "Found %d rows with embeddings in PostgreSQL. "
        "Seeding into Elasticsearch index alias '%s' in batches of %d...",
        total,
        settings.ELASTIC_V2_INDEX_WRITE_ALIAS,
        batch_size,
    )

    client = create_async_elasticsearch_client()
    index = settings.ELASTIC_V2_INDEX_WRITE_ALIAS

    total_success = 0
    total_errors = 0
    offset = 0
    batch_num = 0
    start_time = time.time()

    try:
        uuid_to_es_id = await build_uuid_to_es_id_map(client, index)

        while True:
            rows = await fetch_pg_embeddings(offset=offset, limit=batch_size)
            if not rows:
                break

            batch_num += 1
            success, errors = await bulk_update_es(client, index, rows, uuid_to_es_id)
            total_success += success
            total_errors += errors
            offset += len(rows)

            elapsed = time.time() - start_time
            rate = offset / elapsed if elapsed > 0 else 0
            logger.info(
                "Batch %d: %d/%d seeded (%.1f docs/sec) — %d errors this batch",
                batch_num,
                offset,
                total,
                rate,
                errors,
            )

    finally:
        await client.close()

    elapsed = time.time() - start_time
    logger.info(
        "Done. %d documents seeded, %d errors, %.1f seconds (%.1f docs/sec).",
        total_success,
        total_errors,
        elapsed,
        total_success / elapsed if elapsed > 0 else 0,
    )

    if total_errors > 0:
        logger.warning(
            "%d documents failed to update. Re-run this script to retry.",
            total_errors,
        )
        sys.exit(1)
    else:
        logger.info("All embeddings seeded successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bulk-seed embedding vectors from PostgreSQL into Elasticsearch."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of documents per bulk request (default: {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()
    asyncio.run(main(args.batch_size))
