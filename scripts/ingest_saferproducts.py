from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.saferproducts.client import SaferProductsClient
from app.services.saferproducts.ingestion import (
    ingest_window,
    iter_month_windows,
    sha256_file,
    write_jsonl,
)


class Settings(BaseSettings):
    saferproducts_api_key: str
    saferproducts_base_url: str = (
        "https://www.saferproducts.gov/WebApi/"
        "Cpsc.Cpsrms.Web.Api.svc"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest historical SaferProducts.gov incidents."
    )
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)

    if args.page_size <= 0:
        raise SystemExit("--page-size must be positive.")

    if args.sleep_seconds < 0:
        raise SystemExit("--sleep-seconds cannot be negative.")

    settings = Settings()

    client = SaferProductsClient(
        base_url=settings.saferproducts_base_url,
        application_key=settings.saferproducts_api_key,
    )

    raw_root = Path("data/benchmark/saferproducts/raw")
    processed_root = Path("data/benchmark/saferproducts")
    output_path = processed_root / "incidents.jsonl"
    manifest_path = processed_root / "manifest.json"

    records_by_id: OrderedDict[str, dict] = OrderedDict()
    total_pages = 0
    total_raw = 0
    total_rejected = 0
    window_summaries: list[dict] = []

    print("SafeSKU historical SaferProducts ingestion")
    print("--------------------------------------------")
    print(f"Date range: {start_date} -> {end_date}")
    print(f"Page size: {args.page_size}")

    for window_start, window_end in iter_month_windows(start_date, end_date):
        print(f"\nWindow: {window_start} -> {window_end}")

        result, normalized = ingest_window(
            client,
            start_date=window_start,
            end_date=window_end,
            raw_root=raw_root,
            page_size=args.page_size,
            sleep_seconds=args.sleep_seconds,
        )

        total_pages += result.pages_fetched
        total_raw += result.raw_records
        total_rejected += result.rejected_records

        for record in normalized:
            source_id = record["source_record_id"]
            records_by_id[source_id] = record

        window_summaries.append(
            {
                "start_date": result.start_date.isoformat(),
                "end_date": result.end_date.isoformat(),
                "pages_fetched": result.pages_fetched,
                "raw_records": result.raw_records,
                "normalized_records": result.normalized_records,
                "rejected_records": result.rejected_records,
            }
        )

    records = list(records_by_id.values())
    records.sort(
        key=lambda record: (
            record.get("incident_date") or "",
            record.get("source_record_id") or "",
        )
    )

    write_jsonl(output_path, records)

    manifest = {
        "source": "saferproducts",
        "endpoint": f"{settings.saferproducts_base_url.rstrip('/')}/IncidentDetails",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "page_size": args.page_size,
        "sleep_seconds": args.sleep_seconds,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows": window_summaries,
        "pages_fetched": total_pages,
        "raw_records_fetched": total_raw,
        "normalized_unique_records": len(records),
        "rejected_records": total_rejected,
        "processed_sha256": sha256_file(output_path),
        "pre_recall_eligibility_rule": (
            "incident_date < recall_date AND "
            "publication_date < recall_date"
        ),
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n--------------------------------------------")
    print(f"Windows: {len(window_summaries)}")
    print(f"Pages fetched: {total_pages}")
    print(f"Raw records fetched: {total_raw}")
    print(f"Unique normalized records: {len(records)}")
    print(f"Rejected records: {total_rejected}")
    print(f"Processed SHA-256: {manifest['processed_sha256']}")
    print(f"Incidents: {output_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
