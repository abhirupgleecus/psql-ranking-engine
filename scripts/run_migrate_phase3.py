"""Execute the Phase 3 migration script against the database.

Enables pgvector, adds the embedding column, and creates the HNSW index.

asyncpg does not support multi-statement prepared statements, so we
split the SQL script into individual statements and execute them
one at a time inside a single transaction.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is in python path to support direct script execution
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text

from app.database import engine


MIGRATION_PATH = Path("scripts/migrate_phase3.sql")


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

    print("Phase 3 migration executed successfully.")

    # Verify: check vector extension, embedding column, and HNSW index
    async with engine.connect() as conn:
        # 1. Verify pgvector extension
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        ext = result.first()
        print(f"vector extension: {ext[0] if ext else 'NOT FOUND'}")

        # 2. Verify embedding column exists
        result = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'product_master' AND column_name = 'embedding'"
            )
        )
        col = result.first()
        print(f"embedding column: {col[0] if col else 'NOT FOUND'}")

        # 3. Check how many rows have embeddings (should be 0 initially)
        result = await conn.execute(
            text(
                "SELECT COUNT(*) AS total, "
                "COUNT(embedding) AS with_embedding "
                "FROM product_master"
            )
        )
        row = result.first()
        print(
            f"rows: {row[0]} total, {row[1]} with embeddings"
            if row
            else "no rows found"
        )

        # 4. Verify HNSW index
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'product_master' "
                "AND indexname = 'idx_product_master_embedding'"
            )
        )
        idx = result.first()
        print(f"HNSW index: {idx[0] if idx else 'NOT FOUND'}")


if __name__ == "__main__":
    asyncio.run(main())
