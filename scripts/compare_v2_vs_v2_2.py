#!/usr/bin/env python
import argparse
import json
import os
import sys
import httpx

def get_top_3(results):
    return [(res.get("uuid"), res.get("name")) for res in results[:3]]

def compare_results(v2_top3, v2_2_top3):
    v2_uuids = [item[0] for item in v2_top3]
    v2_2_uuids = [item[0] for item in v2_2_top3]
    
    if not v2_uuids and not v2_2_uuids:
        return "MATCH"
    
    if v2_uuids == v2_2_uuids:
        return "MATCH"
    
    if set(v2_uuids) == set(v2_2_uuids):
        return "PARTIAL"
    
    return "DIFFER"

def main():
    parser = argparse.ArgumentParser(description="Compare v2 vs v2.2 search results.")
    parser.add_argument("--base-url", default="http://localhost:8001", help="Base URL of the target API")
    args = parser.parse_args()

    test_cases_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_cases.json")
    if not os.path.exists(test_cases_path):
        print(f"Error: test_cases.json not found at {test_cases_path}")
        sys.exit(1)

    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    match_count = 0
    partial_count = 0
    differ_count = 0
    skip_count = 0
    total_count = len(test_cases)

    print("=" * 120)
    print(f"Comparing /search/v2 vs /search/v2.2 at {args.base_url}")
    print("=" * 120)

    with httpx.Client(timeout=10.0) as client:
        for idx, case in enumerate(test_cases, 1):
            query = case.get("query")
            category = case.get("category")
            
            params = {"q": query, "top_n": 10}
            if category is not None:
                params["category"] = category

            # Call v2
            v2_url = f"{args.base_url.rstrip('/')}/search/v2"
            v2_top3 = []
            try:
                v2_resp = client.get(v2_url, params=params)
                if v2_resp.status_code == 200:
                    v2_top3 = get_top_3(v2_resp.json().get("results", []))
                else:
                    print(f"[{idx}/{total_count}] v2 Error: HTTP {v2_resp.status_code}")
            except Exception as e:
                print(f"[{idx}/{total_count}] v2 Exception: {e}")

            # Call v2.2
            v2_2_url = f"{args.base_url.rstrip('/')}/search/v2.2"
            v2_2_top3 = []
            v2_2_skipped = False
            try:
                v2_2_resp = client.get(v2_2_url, params=params)
                if v2_2_resp.status_code == 503:
                    v2_2_skipped = True
                elif v2_2_resp.status_code == 200:
                    v2_2_top3 = get_top_3(v2_2_resp.json().get("results", []))
                else:
                    print(f"[{idx}/{total_count}] v2.2 Error: HTTP {v2_2_resp.status_code}")
            except Exception as e:
                print(f"[{idx}/{total_count}] v2.2 Exception: {e}")

            if v2_2_skipped:
                print(f"[{idx}/{total_count}] Query: '{query}'")
                print("    Comparison Status: SKIP (v2.2 / Elastic not configured)")
                print("-" * 120)
                skip_count += 1
                continue

            status = compare_results(v2_top3, v2_2_top3)
            if status == "MATCH":
                match_count += 1
            elif status == "PARTIAL":
                partial_count += 1
            else:
                differ_count += 1

            print(f"[{idx}/{total_count}] Query: '{query}'")
            print(f"    Comparison Status: {status}")
            print(f"    v2 (Top-3):")
            for r_idx, (uuid, name) in enumerate(v2_top3, 1):
                print(f"        {r_idx}. {uuid} | {name}")
            print(f"    v2.2 (Top-3):")
            for r_idx, (uuid, name) in enumerate(v2_2_top3, 1):
                print(f"        {r_idx}. {uuid} | {name}")
            print("-" * 120)

    print("Comparison Summary:")
    print(f"    Total Queries: {total_count}")
    print(f"    MATCH:         {match_count}")
    print(f"    PARTIAL:       {partial_count}")
    print(f"    DIFFER:        {differ_count}")
    if skip_count > 0:
        print(f"    SKIP:          {skip_count} (Elastic not configured)")
    
    valid_comparisons = total_count - skip_count
    match_pct = (match_count / valid_comparisons * 100) if valid_comparisons > 0 else 0.0
    print(f"Result: {match_count}/{valid_comparisons} non-skipped queries have matching top-3 results ({match_pct:.1f}% Match).")
    print("=" * 120)

if __name__ == "__main__":
    main()
