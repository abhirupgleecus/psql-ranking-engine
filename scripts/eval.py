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
        expected_ids = case.get("expected_top3_ids")
        if not isinstance(expected_ids, list) or not expected_ids:
            raise ValueError(
                f"Test case #{index} must include a non-empty expected_top3_ids list."
            )
        if not all(isinstance(product_id, str) and product_id for product_id in expected_ids):
            raise ValueError(
                f"Test case #{index} has an invalid product ID in expected_top3_ids."
            )

    return data


def evaluate_case(client: httpx.Client, base_url: str, case: dict) -> bool:
    query = case["query"]
    expected_ids = case["expected_top3_ids"]
    description = case["description"]

    try:
        response = client.get(
            f"{base_url}/search",
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
    returned_ids = [
        result.get("id")
        for result in results[:3]
        if isinstance(result, dict) and result.get("id")
    ]

    missing_ids = [
        product_id
        for product_id in expected_ids
        if product_id not in returned_ids
    ]

    if missing_ids:
        print(
            f"FAIL | {query} | {description} | "
            f"missing ids: {missing_ids} | returned ids: {returned_ids}"
        )
        return False

    print(
        f"PASS | {query} | {description} | "
        f"returned ids: {returned_ids}"
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
    args = parser.parse_args()

    test_cases = load_test_cases(DEFAULT_TEST_CASES_PATH)
    base_url = args.base_url.rstrip("/")

    passed_cases = 0

    with httpx.Client(timeout=10.0) as client:
        for case in test_cases:
            if evaluate_case(client, base_url, case):
                passed_cases += 1

    total_cases = len(test_cases)
    accuracy = (passed_cases / total_cases * 100) if total_cases else 0.0

    print(
        f"Accuracy: {passed_cases}/{total_cases} cases passed = {accuracy:.1f}%"
    )

    return 0 if accuracy >= 90.0 else 1


if __name__ == "__main__":
    sys.exit(main())
