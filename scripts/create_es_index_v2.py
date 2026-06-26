"""Create the versioned Elasticsearch index and v2 aliases.

This script intentionally uses only the Python standard library so it can run
before the Elasticsearch Python client dependency is added to the project.

Required environment variables:

- ELASTIC_URL
- ELASTIC_API_KEY

Optional environment variables:

- ELASTIC_V2_INDEX_NAME (default: product_master_v2_0001)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import error, request


DEFAULT_INDEX_NAME = "product_master_v2_0001"
MAPPING_PATH = (
    Path(__file__).resolve().parent / "es" / "product_master_v2_mapping.json"
)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _load_mapping(index_name: str) -> bytes:
    payload = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    payload.setdefault("aliases", {})
    payload["aliases"].setdefault("product_master_v2_read", {})
    payload["aliases"]["product_master_v2_write"] = {"is_write_index": True}
    return json.dumps(payload, indent=2).encode("utf-8")


def _perform_request(method: str, url: str, api_key: str | None, body: bytes | None = None) -> tuple[int, str]:
    req = request.Request(url=url, data=body, method=method)
    if api_key:
        req.add_header("Authorization", f"ApiKey {api_key}")
    req.add_header("Content-Type", "application/json")

    try:
        with request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        return exc.code, message


def main() -> int:
    try:
        elastic_url = _require_env("ELASTIC_URL").rstrip("/")
        api_key = os.getenv("ELASTIC_API_KEY")
        index_name = os.getenv("ELASTIC_V2_INDEX_NAME", DEFAULT_INDEX_NAME)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not MAPPING_PATH.exists():
        print(f"Mapping file not found: {MAPPING_PATH}", file=sys.stderr)
        return 1

    body = _load_mapping(index_name)
    create_url = f"{elastic_url}/{index_name}"

    print(f"Creating index: {index_name}")
    status, response_body = _perform_request("PUT", create_url, api_key, body)

    if status in {200, 201}:
        print("Index created successfully.")
        print(response_body)
        return 0

    if status == 400 and "resource_already_exists_exception" in response_body:
        print("Index already exists.")
        print(response_body)
        return 0

    print(f"Failed to create index. HTTP {status}", file=sys.stderr)
    print(response_body, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
