"""Main pipeline orchestrator for Ghost Data Still Exists Deletion-Audit Agent."""

import argparse
import json
import sys
from pathlib import Path
import pandas as pd
from tqdm import tqdm

# Ensure UTF-8 stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add code dir to sys.path
CODE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CODE_DIR.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import config
from data_loader import data_loader
from identity_index import identity_index
from identity_resolver import identity_resolver
from intent_classifier import intent_classifier
from evidence_gatherer import evidence_gatherer
from policy_engine import policy_engine
from usage_tracker import usage_tracker


def process_case(row: pd.Series) -> dict:
    case_id = str(row["case_id"])
    email = str(row.get("email", "")).strip()
    audit_at = str(row.get("audit_at", ""))
    request_text = str(row.get("request_text", ""))

    # 1. Intent classification
    is_authorized, reason = intent_classifier.is_deletion_authorized(case_id, request_text)
    if not is_authorized:
        return {
            "case_id": case_id,
            "deletion_status": "NOT_APPLICABLE",
            "steps_json": "[]",
        }

    # 2. Identity resolution
    identity = identity_resolver.resolve(email, fallback_query=request_text)

    # 3. Evidence gathering
    resources = []
    if identity:
        requested_at = str(row.get("requested_at", ""))
        reported_at = str(row.get("reported_at", ""))
        resources = evidence_gatherer.gather_user_resources(
            identity,
            audit_at=audit_at,
            requested_at=requested_at,
            reported_at=reported_at,
        )

    # 4. Policy evaluation & step generation
    status, steps = policy_engine.evaluate_case(
        case_id=case_id,
        identity=identity,
        resources=resources,
        is_deletion_authorized=is_authorized,
    )

    return {
        "case_id": case_id,
        "deletion_status": status,
        "steps_json": json.dumps(steps, separators=(",", ":")),
    }


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists Deletion-Audit Agent")
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Run only on sample_deletion_requests.csv for testing/validation",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output CSV path (defaults to repo root output.csv)",
    )
    args = parser.parse_args()

    print("[*] Initializing SQLite database and indexing CSV data...")
    data_loader.init_database()

    print("[*] Building/loading FAISS identity index with MiniLM embeddings...")
    identity_index.build_index()

    # Load requests
    sample_only = args.sample_only
    requests_df = data_loader.get_deletion_requests_df(sample_only=sample_only)
    total_cases = len(requests_df)
    print(f"[*] Processing {total_cases} requests ({'sample' if sample_only else 'full'} dataset)...")

    results = []
    for _, row in tqdm(requests_df.iterrows(), total=total_cases, desc="Auditing Cases"):
        res = process_case(row)
        results.append(res)

    out_df = pd.DataFrame(results)
    
    # Sort by case_id
    # Handle natural sort for case_XX
    def sort_key(cid: str):
        parts = cid.split("_")
        return (parts[0], int(parts[1])) if len(parts) > 1 and parts[1].isdigit() else (cid, 0)

    out_df["_sort"] = out_df["case_id"].apply(sort_key)
    out_df = out_df.sort_values(by="_sort").drop(columns=["_sort"]).reset_index(drop=True)

    # Determine output path
    if args.output:
        out_path = Path(args.output)
    elif sample_only:
        out_path = config.repo_root / "sample_test_output.csv"
    else:
        out_path = config.output_csv_path

    out_df.to_csv(out_path, index=False, columns=["case_id", "deletion_status", "steps_json"])
    print(f"[+] Output written to {out_path} ({len(out_df)} rows)")

    # Write usage report
    usage_report_path = config.repo_root / "code" / "evaluation" / "usage_report.md"
    usage_tracker.write_usage_report(usage_report_path, num_requests=total_cases)
    print(f"[+] Usage report generated at {usage_report_path}")


if __name__ == "__main__":
    main()
