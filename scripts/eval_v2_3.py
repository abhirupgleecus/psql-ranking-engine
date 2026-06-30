#!/usr/bin/env python
"""Evaluation harness for /search/v2.3 (Elasticsearch hybrid: BM25 + KNN + native RRF).

Loads test_cases.json and issues live requests to /search/v2.3, checking
whether expected product UUIDs appear in the returned top 3 results.

Usage:
    .venv/Scripts/python.exe scripts/eval_v2_3.py
    .venv/Scripts/python.exe scripts/eval_v2_3.py --base-url http://8.231.91.185:8001
"""

import argparse
import json
import os
import sys

import httpx


def main():
    parser = argparse.ArgumentParser(
        description="Run v2.3 evaluation harness against Elasticsearch hybrid search."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="Base URL of the target API (default: http://localhost:8001)",
    )
    args = parser.parse_args()

    test_cases_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "test_cases.json",
    )
    if not os.path.exists(test_cases_path):
        print(f"Error: test_cases.json not found at {test_cases_path}")
        sys.exit(1)

    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    passed_count = 0
    total_count = len(test_cases)

    print("=" * 80)
    print(f"Running v2.3 Evaluation against {args.base_url}/search/v2.3")
    print("=" * 80)

    with httpx.Client(timeout=30.0) as client:
        for idx, case in enumerate(test_cases, 1):
            query = case.get("query")
            expected_uuids = case.get("expected_top3_uuids", [])
            category = case.get("category")
            description = case.get("description", "")

            params = {"q": query, "top_n": 10}
            if category is not None:
                params["category"] = category

            url = f"{args.base_url.rstrip('/')}/search/v2.3"
            try:
                response = client.get(url, params=params)
                if response.status_code != 200:
                    print(f"[{idx}/{total_count}] FAIL - Query: '{query}'")
                    print(f"    Error: HTTP {response.status_code} - {response.text}")
                    print("-" * 80)
                    continue

                data = response.json()
                search_mode = data.get("search_mode", "unknown")
                rrf_k = data.get("rrf_k", "?")
                candidate_multiplier = data.get("candidate_multiplier", "?")
                results = data.get("results", [])
                top_3_uuids = [res.get("uuid") for res in results[:3]]

                matched = all(uuid in top_3_uuids for uuid in expected_uuids)

                if matched:
                    passed_count += 1
                    status = "PASS"
                else:
                    status = "FAIL"

                print(f"[{idx}/{total_count}] {status} - Query: '{query}'")
                print(f"    Description:        {description}")
                print(f"    Mode:               {search_mode}  (rrf_k={rrf_k}, multiplier={candidate_multiplier})")
                print(f"    Expected:           {expected_uuids}")
                print(f"    Got (Top 3):        {top_3_uuids}")
                if not matched:
                    print(f"    Got (All results):  {[res.get('uuid') for res in results]}")
                print("-" * 80)

            except Exception as e:
                print(f"[{idx}/{total_count}] FAIL - Query: '{query}'")
                print(f"    Exception: {e}")
                print("-" * 80)

    accuracy = (passed_count / total_count) * 100 if total_count > 0 else 0.0
    print(f"Accuracy Summary: {passed_count}/{total_count} cases passed = {accuracy:.1f}%")

    if accuracy >= 90.0:
        print("Evaluation PASSED (meets 90% accuracy threshold).")
        sys.exit(0)
    else:
        print("Evaluation FAILED (below 90% accuracy threshold).")
        sys.exit(1)


if __name__ == "__main__":
    main()
