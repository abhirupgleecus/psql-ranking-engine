import argparse
import json
import sys
from pathlib import Path

import httpx


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TEST_CASES_PATH = Path(__file__).resolve().parent.parent / "test_cases.json"


def load_test_cases(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("test_cases.json must contain a JSON array.")

    for index, case in enumerate(data, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"Test case #{index} must be an object.")
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError(f"Test case #{index} must include a non-empty query.")
        if not isinstance(case.get("description"), str) or not case["description"].strip():
            raise ValueError(
                f"Test case #{index} must include a non-empty description."
            )
        expected_uuids = case.get("expected_top3_uuids")
        if not isinstance(expected_uuids, list) or not expected_uuids:
            raise ValueError(
                f"Test case #{index} must include a non-empty expected_top3_uuids list."
            )
        if not all(isinstance(product_uuid, str) and product_uuid for product_uuid in expected_uuids):
            raise ValueError(
                f"Test case #{index} has an invalid product UUID in expected_top3_uuids."
            )

    return data


def evaluate_case(client: httpx.Client, base_url: str, case: dict, engine: str) -> bool:
    query = case["query"]
    expected_uuids = case["expected_top3_uuids"]
    description = case["description"]

    path = "/search/v2" if engine == "v2" else "/search"

    try:
        response = client.get(
            f"{base_url}{path}",
            params={"q": query, "top_n": 3},
        )
    except httpx.HTTPError as exc:
        print(f"FAIL | {query} | {description} | request error: {exc}")
        return False

    if response.status_code != 200:
        print(
            f"FAIL | {query} | {description} | "
            f"HTTP {response.status_code}: {response.text}"
        )
        return False

    payload = response.json()
    results = payload.get("results", [])
    returned_uuids = [
        result.get("uuid")
        for result in results[:3]
        if isinstance(result, dict) and result.get("uuid")
    ]

    missing_uuids = [
        product_uuid
        for product_uuid in expected_uuids
        if product_uuid not in returned_uuids
    ]

    if missing_uuids:
        print(
            f"FAIL | {query} | {description} | "
            f"missing uuids: {missing_uuids} | returned uuids: {returned_uuids}"
        )
        return False

    # For v2, let's print the search mode used for additional visibility
    mode_str = f" [mode: {payload.get('search_mode')}]" if engine == "v2" else ""
    print(
        f"PASS | {query} | {description}{mode_str} | "
        f"returned uuids: {returned_uuids}"
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate search ranking accuracy against top-3 expectations.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL for the running API. Defaults to {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--engine",
        choices=["v1", "v2"],
        default="v1",
        help="Search engine to evaluate (v1 or v2). Defaults to v1.",
    )
    args = parser.parse_args()

    test_cases = load_test_cases(DEFAULT_TEST_CASES_PATH)
    base_url = args.base_url.rstrip("/")

    passed_cases = 0

    with httpx.Client(timeout=10.0) as client:
        for case in test_cases:
            if evaluate_case(client, base_url, case, args.engine):
                passed_cases += 1

    total_cases = len(test_cases)
    accuracy = (passed_cases / total_cases * 100) if total_cases else 0.0

    print(
        f"Accuracy: {passed_cases}/{total_cases} cases passed = {accuracy:.1f}%"
    )

    return 0 if accuracy >= 90.0 else 1


if __name__ == "__main__":
    sys.exit(main())
