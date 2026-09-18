from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.saferproducts.client import SaferProductsClient
from app.services.saferproducts.ingestion import (
    build_filter,
    ingest_window,
    iter_month_windows,
    load_raw_window,
    merge_window_outputs,
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
        description="Resumable historical SaferProducts.gov ingestion."
    )
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse complete raw windows and continue partial raw windows.",
    )
    return parser.parse_args()


def write_partial_manifest(
    path: Path,
    *,
    start_date: date,
    end_date: date,
    page_size: int,
    sleep_seconds: float,
    window_summaries: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "partial",
        "source": "saferproducts",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "page_size": page_size,
        "sleep_seconds": sleep_seconds,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "completed_windows": window_summaries,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


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
    windows_root = processed_root / "windows"
    output_path = processed_root / "incidents.jsonl"
    manifest_path = processed_root / "manifest.json"
    partial_manifest_path = processed_root / "manifest.partial.json"

    window_summaries: list[dict[str, Any]] = []
    window_paths: list[Path] = []

    print("SafeSKU historical SaferProducts ingestion")
    print("--------------------------------------------")
    print(f"Date range: {start_date} -> {end_date}")
    print(f"Page size: {args.page_size}")
    print(f"Resume mode: {args.resume}")

    try:
        for window_start, window_end in iter_month_windows(
            start_date,
            end_date,
        ):
            print(f"\nWindow: {window_start} -> {window_end}")

            window_root = raw_root / window_start.isoformat()
            existing_state = (
                load_raw_window(window_root) if args.resume else None
            )

            if existing_state and existing_state.records:
                print(f"  Existing raw records: {len(existing_state.records)}")
                print(f"  Existing raw pages: {existing_state.page_count}")
                print(
                    "  Existing expected total: "
                    f"{existing_state.expected_total}"
                )

            result, normalized = ingest_window(
                client,
                start_date=window_start,
                end_date=window_end,
                raw_root=raw_root,
                page_size=args.page_size,
                sleep_seconds=args.sleep_seconds,
                existing_state=existing_state,
            )

            window_path = windows_root / f"{window_start.isoformat()}.jsonl"
            write_jsonl(window_path, normalized)
            window_paths.append(window_path)

            summary = {
                "start_date": result.start_date.isoformat(),
                "end_date": result.end_date.isoformat(),
                "pages_fetched_or_reused": result.pages_fetched,
                "raw_records": result.raw_records,
                "normalized_records": result.normalized_records,
                "rejected_records": result.rejected_records,
                "resumed_from_skip": result.resumed_from_skip,
                "reused_existing_raw": result.reused_raw_pages,
                "filter": build_filter(window_start, window_end),
            }
            window_summaries.append(summary)

            write_partial_manifest(
                partial_manifest_path,
                start_date=start_date,
                end_date=end_date,
                page_size=args.page_size,
                sleep_seconds=args.sleep_seconds,
                window_summaries=window_summaries,
            )

    except KeyboardInterrupt:
        print("\nIngestion interrupted safely.")
        print(
            "Raw pages already written are preserved. "
            "Re-run with --resume to continue."
        )
        raise SystemExit(130)

    records = merge_window_outputs(window_paths)
    write_jsonl(output_path, records)

    manifest = {
        "status": "complete",
        "source": "saferproducts",
        "endpoint": (
            f"{settings.saferproducts_base_url.rstrip('/')}/IncidentDetails"
        ),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "page_size": args.page_size,
        "sleep_seconds": args.sleep_seconds,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "windows": window_summaries,
        "pages_fetched_or_reused": sum(
            item["pages_fetched_or_reused"]
            for item in window_summaries
        ),
        "raw_records_fetched_or_reused": sum(
            item["raw_records"] for item in window_summaries
        ),
        "normalized_unique_records": len(records),
        "rejected_records": sum(
            item["rejected_records"]
            for item in window_summaries
        ),
        "processed_sha256": sha256_file(output_path),
        "pre_recall_eligibility_rule": (
            "incident_date < recall_date AND "
            "publication_date < recall_date"
        ),
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if partial_manifest_path.exists():
        partial_manifest_path.unlink()

    print("\n--------------------------------------------")
    print("Historical SaferProducts ingestion complete")
    print(f"Windows: {len(window_summaries)}")
    print(
        "Pages fetched/reused: "
        f"{manifest['pages_fetched_or_reused']}"
    )
    print(
        "Raw records fetched/reused: "
        f"{manifest['raw_records_fetched_or_reused']}"
    )
    print(f"Unique normalized records: {len(records)}")
    print(f"Rejected records: {manifest['rejected_records']}")
    print(f"Processed SHA-256: {manifest['processed_sha256']}")
    print(f"Incidents: {output_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
