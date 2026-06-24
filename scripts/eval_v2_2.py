#!/usr/bin/env python
import argparse
import json
import os
import sys
import httpx

def main():
    parser = argparse.ArgumentParser(description="Run v2.2 evaluation harness against Elasticsearch search.")
    parser.add_argument("--base-url", default="http://localhost:8001", help="Base URL of the target API")
    args = parser.parse_args()

    test_cases_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_cases.json")
    if not os.path.exists(test_cases_path):
        print(f"Error: test_cases.json not found at {test_cases_path}")
        sys.exit(1)

    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    passed_count = 0
    skipped_count = 0
    evaluated_count = 0
    total_count = len(test_cases)
    
    print("=" * 80)
    print(f"Running v2.2 Evaluation against {args.base_url}/search/v2.2")
    print("=" * 80)

    with httpx.Client(timeout=10.0) as client:
        for idx, case in enumerate(test_cases, 1):
            query = case.get("query")
            expected_uuids = case.get("expected_top3_uuids", [])
            category = case.get("category")
            description = case.get("description", "")

            params = {
                "q": query,
                "top_n": 10
            }
            if category is not None:
                params["category"] = category

            url = f"{args.base_url.rstrip('/')}/search/v2.2"
            try:
                response = client.get(url, params=params)
                if response.status_code == 503:
                    print(f"[{idx}/{total_count}] SKIP - Query: '{query}' (Elastic not configured)")
                    print("-" * 80)
                    skipped_count += 1
                    continue
                
                if response.status_code != 200:
                    print(f"[{idx}/{total_count}] FAIL - Query: '{query}'")
                    print(f"    Error: HTTP {response.status_code} - {response.text}")
                    print("-" * 80)
                    evaluated_count += 1
                    continue
                
                evaluated_count += 1
                data = response.json()
                search_mode = data.get("search_mode", "unknown")
                results = data.get("results", [])
                top_3_uuids = [res.get("uuid") for res in results[:3]]

                # Check if all expected UUIDs are in top 3
                matched = True
                for uuid in expected_uuids:
                    if uuid not in top_3_uuids:
                        matched = False
                        break
                
                if matched:
                    passed_count += 1
                    status = "PASS"
                else:
                    status = "FAIL"

                print(f"[{idx}/{total_count}] {status} - Query: '{query}'")
                print(f"    Description: {description}")
                print(f"    Mode:        {search_mode}")
                print(f"    Expected:    {expected_uuids}")
                print(f"    Got (Top 3): {top_3_uuids}")
                if not matched:
                    print(f"    Got (All 10): {[res.get('uuid') for res in results]}")
                print("-" * 80)
            except Exception as e:
                print(f"[{idx}/{total_count}] FAIL - Query: '{query}'")
                print(f"    Exception: {e}")
                print("-" * 80)
                evaluated_count += 1

    if skipped_count == total_count:
        print("All cases skipped. Elasticsearch is not configured.")
        sys.exit(0)

    accuracy = (passed_count / evaluated_count) * 100 if evaluated_count > 0 else 0.0
    print(f"Accuracy Summary: {passed_count}/{evaluated_count} evaluated cases passed = {accuracy:.1f}% ({skipped_count} skipped)")
    
    if accuracy >= 90.0:
        print("Evaluation PASSED (meets 90% accuracy threshold).")
        sys.exit(0)
    else:
        print("Evaluation FAILED (below 90% accuracy threshold).")
        sys.exit(1)

if __name__ == "__main__":
    main()
