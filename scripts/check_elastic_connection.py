"""Verify connectivity to the configured Elastic deployment."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv


project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")
sys.path.insert(0, str(project_root))

from app.elastic_client import get_elastic_info, get_elastic_target


async def main() -> int:
    try:
        info = await get_elastic_info()
    except Exception as exc:
        print(f"Elastic connection check failed: {exc}", file=sys.stderr)
        return 1

    print(f"Connected to Elastic target: {get_elastic_target()}")
    print(f"Cluster name: {info.get('cluster_name')}")
    print(f"Cluster UUID: {info.get('cluster_uuid')}")
    version = info.get("version", {})
    print(f"Version: {version.get('number')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
