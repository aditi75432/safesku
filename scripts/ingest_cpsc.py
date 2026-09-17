from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"

# The backend package lives under apps/api.
# Add that directory so this standalone ingestion script can import app.*.
sys.path.insert(0, str(API_ROOT))


from app.core.config import get_settings
from app.services.recalls.client import CPSCClient
from app.services.recalls.service import RecallIngestionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest CPSC recalls into SafeSKU.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    settings = get_settings()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_output = PROJECT_ROOT / "data" / "raw" / "cpsc" / f"recalls_{stamp}.json"
    processed_output = PROJECT_ROOT / "data" / "processed" / "cpsc" / "recalls.jsonl"

    service = RecallIngestionService(CPSCClient(settings.cpsc_recall_base_url))
    fetched, normalized, rejected = service.ingest(
        start_date=args.start_date, end_date=args.end_date,
        raw_output=raw_output, processed_output=processed_output,
    )

    print("SafeSKU CPSC ingestion")
    print("-----------------------")
    print(f"Source: {settings.cpsc_recall_base_url}")
    print(f"Date range: {args.start_date} -> {args.end_date}")
    print(f"Fetched recalls: {fetched}")
    print(f"Normalized recalls: {normalized}")
    print(f"Rejected recalls: {rejected}")
    print(f"Raw snapshot: {raw_output.relative_to(PROJECT_ROOT)}")
    print(f"Processed data: {processed_output.relative_to(PROJECT_ROOT)}")

if __name__ == "__main__":
    main()
