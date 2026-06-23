"""Execute the PostgreSQL CDC prep migration script against the database.

Sets replica identity and creates the logical replication publication.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is in python path to support direct script execution
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.database import engine

MIGRATION_PATH = Path("scripts/migrate_postgres_cdc.sql")


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
    if not MIGRATION_PATH.exists():
        print(f"Migration script not found: {MIGRATION_PATH}", file=sys.stderr)
        sys.exit(1)

    script = MIGRATION_PATH.read_text(encoding="utf-8")
    statements = split_sql_statements(script)

    print(f"Executing {len(statements)} SQL statement(s) from {MIGRATION_PATH}...")

    async with engine.begin() as conn:
        for i, stmt in enumerate(statements, 1):
            # Show first line of each statement for visibility
            first_line = stmt.split("\n")[0][:80]
            print(f"  [{i}/{len(statements)}] {first_line}...")
            await conn.execute(text(stmt))

    print("PostgreSQL CDC prep migration executed successfully.")

    # Verification checks
    print("\nVerifying database state...")
    async with engine.connect() as conn:
        # 1. Verify replica identity on product_master
        result = await conn.execute(
            text(
                "SELECT relreplident "
                "FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'product_master';"
            )
        )
        row = result.first()
        if row:
            # Relreplident options: d = default, n = nothing, f = full, i = index
            identity_char = row[0]
            identity_map = {'d': 'default', 'n': 'nothing', 'f': 'full', 'i': 'index'}
            print(f"  Replica Identity of 'product_master': {identity_map.get(identity_char, identity_char)}")
        else:
            print("  Table 'product_master' NOT FOUND")

        # 2. Verify publication exists
        result = await conn.execute(
            text("SELECT pubname FROM pg_publication WHERE pubname = 'dbz_pub_product_master_v2';")
        )
        row = result.first()
        print(f"  Publication 'dbz_pub_product_master_v2': {'FOUND' if row else 'NOT FOUND'}")


if __name__ == "__main__":
    asyncio.run(main())
