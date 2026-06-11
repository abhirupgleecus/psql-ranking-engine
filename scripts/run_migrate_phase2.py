"""Execute the Phase 2 migration script against the database.

asyncpg does not support multi-statement prepared statements, so we
split the SQL script into individual statements and execute them
one at a time inside a single transaction.
"""

import asyncio
import re
from pathlib import Path

from sqlalchemy import text

from app.database import engine


MIGRATION_PATH = Path("scripts/migrate_phase2.sql")


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

    print("Phase 2 migration executed successfully.")

    # Verify: check search_vector column exists and is populated
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT search_vector IS NOT NULL AS has_vector "
                "FROM product_master LIMIT 1"
            )
        )
        row = result.first()
        print(f"search_vector populated: {row[0] if row else 'no rows'}")

        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'product_master' "
                "AND indexname = 'idx_product_master_search_vector'"
            )
        )
        idx = result.first()
        print(f"GIN index present: {idx[0] if idx else 'NOT FOUND'}")

        # Verify pg_trgm extension
        result = await conn.execute(
            text(
                "SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'"
            )
        )
        ext = result.first()
        print(f"pg_trgm extension: {ext[0] if ext else 'NOT FOUND'}")


if __name__ == "__main__":
    asyncio.run(main())
