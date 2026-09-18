from __future__ import annotations

import argparse
import hashlib
import json
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.core.config import get_settings
from app.models.recall import RecallRecord
from app.services.recalls.client import CPSCClient
from app.services.recalls.normalizer import normalize_recall


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a reproducible historical CPSC benchmark without overwriting "
            "the live/demo CPSC dataset."
        )
    )
    parser.add_argument("--start-date", required=True, help="Inclusive YYYY-MM-DD date")
    parser.add_argument("--end-date", required=True, help="Inclusive YYYY-MM-DD date")
    parser.add_argument(
        "--chunk-months",
        type=int,
        default=3,
        help="Number of calendar months per API request (default: 3)",
    )
    return parser.parse_args()


def parse_date(value: str, *, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}; expected YYYY-MM-DD") from exc


def add_months(value: date, months: int) -> date:
    if months < 0:
        raise ValueError("months must be non-negative")

    month_index = (value.year * 12 + value.month - 1) + months
    year, month_zero_based = divmod(month_index, 12)
    month = month_zero_based + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def iter_date_windows(start: date, end: date, chunk_months: int) -> Iterator[tuple[date, date]]:
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if chunk_months < 1:
        raise ValueError("chunk_months must be at least 1")

    current = start
    while current <= end:
        next_boundary = add_months(current, chunk_months)
        window_end = min(end, next_boundary - timedelta(days=1))
        yield current, window_end
        current = window_end + timedelta(days=1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_jsonl(path: Path, records: list[RecallRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(
                json.dumps(record.model_dump(mode="json"), ensure_ascii=False)
                + "\n"
            )


def main() -> None:
    args = parse_args()
    start_date = parse_date(args.start_date, field_name="start-date")
    end_date = parse_date(args.end_date, field_name="end-date")

    settings = get_settings()
    client = CPSCClient(settings.cpsc_recall_base_url)

    raw_dir = PROJECT_ROOT / "data" / "raw" / "cpsc_benchmark"
    benchmark_dir = PROJECT_ROOT / "data" / "benchmark" / "cpsc"
    raw_dir.mkdir(parents=True, exist_ok=True)
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    all_normalized: dict[str, RecallRecord] = {}
    chunk_summaries: list[dict[str, Any]] = []
    rejected_records = 0
    fetched_records = 0

    for window_start, window_end in iter_date_windows(
        start_date,
        end_date,
        args.chunk_months,
    ):
        raw_records = client.search_recalls(
            start_date=window_start.isoformat(),
            end_date=window_end.isoformat(),
        )
        fetched_records += len(raw_records)

        raw_path = raw_dir / (
            f"recalls_{window_start:%Y%m%d}_{window_end:%Y%m%d}.json"
        )
        write_json(raw_path, raw_records)

        chunk_rejected = 0
        chunk_ids: list[str] = []

        for raw_record in raw_records:
            try:
                normalized = normalize_recall(raw_record)
            except (TypeError, ValueError):
                chunk_rejected += 1
                continue

            chunk_ids.append(normalized.source_record_id)
            all_normalized.setdefault(normalized.source_record_id, normalized)

        rejected_records += chunk_rejected
        chunk_summaries.append(
            {
                "start_date": window_start.isoformat(),
                "end_date": window_end.isoformat(),
                "fetched_records": len(raw_records),
                "accepted_records": len(raw_records) - chunk_rejected,
                "rejected_records": chunk_rejected,
                "source_record_ids": sorted(set(chunk_ids)),
                "raw_snapshot": str(raw_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                "raw_sha256": sha256_file(raw_path),
            }
        )

    normalized_records = sorted(
        all_normalized.values(),
        key=lambda record: (
            record.recall_date or date.max,
            record.source_record_id,
        ),
    )

    processed_path = benchmark_dir / "recalls.jsonl"
    manifest_path = benchmark_dir / "manifest.json"
    write_jsonl(processed_path, normalized_records)

    recall_dates = [
        record.recall_date.isoformat()
        for record in normalized_records
        if record.recall_date is not None
    ]

    manifest = {
        "pipeline": "cpsc_historical_benchmark_v1",
        "source": "cpsc",
        "source_endpoint": settings.cpsc_recall_base_url,
        "selection": {
            "rule": "all recall API records whose RecallDate falls inside the requested inclusive window",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "chunk_months": args.chunk_months,
            "deduplication_key": "source_record_id",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_fetched_records": fetched_records,
        "unique_normalized_records": len(normalized_records),
        "rejected_records": rejected_records,
        "recall_date_min": min(recall_dates) if recall_dates else None,
        "recall_date_max": max(recall_dates) if recall_dates else None,
        "processed_sha256": sha256_file(processed_path),
        "chunks": chunk_summaries,
        "notes": [
            "This benchmark is separate from data/processed/cpsc/recalls.jsonl used by the live/demo pipeline.",
            "Recall Number is not used as a deduplication key because multiple source records may legitimately share a recall number.",
            "Raw API responses are retained per date window for reproducibility.",
        ],
    }
    write_json(manifest_path, manifest)

    print("SafeSKU historical CPSC benchmark")
    print("----------------------------------")
    print(f"Date range: {start_date} -> {end_date}")
    print(f"Chunk size: {args.chunk_months} month(s)")
    print(f"API-fetched records: {fetched_records}")
    print(f"Unique normalized records: {len(normalized_records)}")
    print(f"Rejected records: {rejected_records}")
    print(f"Processed SHA-256: {manifest['processed_sha256']}")
    print(f"Raw snapshots: {raw_dir.relative_to(PROJECT_ROOT)}")
    print(f"Benchmark recalls: {processed_path.relative_to(PROJECT_ROOT)}")
    print(f"Manifest: {manifest_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
