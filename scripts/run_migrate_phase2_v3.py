"""Execute the Phase 2v3 migration script against the database.

Adds the GIN trigram index on upc and re-weights the search_vector generated column.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is in python path to support direct script execution
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.database import engine

MIGRATION_PATH = Path("scripts/migrate_phase2_v3.sql")


def split_sql_statements(script: str) -> list[str]:
    """Split a SQL script into individual executable statements.

    Handles DO $$ ... $$ blocks and functions as single statements.
    """
    statements: list[str] = []
    current_statement: list[str] = []
    in_dollar_block = False

    for line in script.splitlines():
        stripped = line.strip()
        # Skip comments and empty lines outside dollar blocks
        if not in_dollar_block and (not stripped or stripped.startswith("--")):
            continue

        current_statement.append(line)

        # Toggle dollar block state when encountering $$
        if "$$" in line:
            in_dollar_block = not in_dollar_block

        # If we are not in a dollar block and the statement ends with a semicolon
        if not in_dollar_block and stripped.endswith(";"):
            statements.append("\n".join(current_statement).strip())
            current_statement = []

    if current_statement:
        stmt = "\n".join(current_statement).strip()
        if stmt:
            statements.append(stmt)

    return statements


async def main() -> None:
    script = MIGRATION_PATH.read_text(encoding="utf-8")
    statements = split_sql_statements(script)

    print(f"Executing {len(statements)} SQL statement(s)...")

    async with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            # Show first line of each statement for visibility
            first_line = stmt.split("\n")[0][:80]
            print(f"  [{i}/{len(statements)}] {first_line}...")
            await conn.execute(text(stmt))

    print("Phase 2v3 migration executed successfully.")

    # Verify: check search_vector column exists, is populated, and index/trgm index exist.
    async with engine.connect() as conn:
        # 1. Verify pg_trgm extension
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
        )
        ext = result.first()
        print(f"pg_trgm extension: {ext[0] if ext else 'NOT FOUND'}")

        # 2. Verify upc trigram index exists
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'product_master' "
                "AND indexname = 'idx_product_master_upc_trgm'"
            )
        )
        idx_trgm = result.first()
        print(f"upc trigram index: {idx_trgm[0] if idx_trgm else 'NOT FOUND'}")

        # 3. Verify search_vector is populated
        result = await conn.execute(
            text(
                "SELECT search_vector IS NOT NULL AS has_vector "
                "FROM product_master LIMIT 1"
            )
        )
        row = result.first()
        print(f"search_vector populated: {row[0] if row else 'no rows'}")

        # 4. Verify search_vector index exists
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'product_master' "
                "AND indexname = 'idx_product_master_search_vector'"
            )
        )
        idx_search = result.first()
        print(f"search_vector index: {idx_search[0] if idx_search else 'NOT FOUND'}")


if __name__ == "__main__":
    asyncio.run(main())
