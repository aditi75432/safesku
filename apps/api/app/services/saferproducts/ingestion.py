from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from app.services.saferproducts.client import SaferProductsClient
from app.services.saferproducts.normalizer import normalize_incident


@dataclass(frozen=True)
class IngestionWindowResult:
    start_date: date
    end_date: date
    pages_fetched: int
    raw_records: int
    normalized_records: int
    rejected_records: int


def next_month(value: date) -> date:
    """Return the first day of the following calendar month."""
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def iter_month_windows(
    start_date: date,
    end_date: date,
) -> list[tuple[date, date]]:
    """Split a date range into half-open calendar-month windows."""
    if end_date <= start_date:
        raise ValueError("end_date must be after start_date.")

    windows: list[tuple[date, date]] = []
    cursor = date(start_date.year, start_date.month, 1)

    while cursor < end_date:
        window_end = min(next_month(cursor), end_date)
        effective_start = max(cursor, start_date)
        windows.append((effective_start, window_end))
        cursor = window_end

    return windows


def odata_datetime(value: date) -> str:
    return f"datetime'{value.isoformat()}T00:00:00'"


def build_filter(start_date: date, end_date: date) -> str:
    """Build the bounded IncidentDate OData filter."""
    return (
        f"IncidentDate ge {odata_datetime(start_date)} "
        f"and IncidentDate lt {odata_datetime(end_date)}"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True)
            )
            handle.write("\n")


def ingest_window(
    client: SaferProductsClient,
    *,
    start_date: date,
    end_date: date,
    raw_root: Path,
    page_size: int,
    sleep_seconds: float,
    log: Callable[[str], None] = print,
) -> tuple[IngestionWindowResult, list[dict[str, Any]]]:
    """Fetch, snapshot, normalize, and return one date window."""
    if page_size <= 0:
        raise ValueError("page_size must be positive.")
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds cannot be negative.")
    if end_date <= start_date:
        raise ValueError("end_date must be after start_date.")

    filter_expression = build_filter(start_date, end_date)
    order_by = "IncidentDate asc,IncidentReportNumber asc"

    window_root = raw_root / start_date.isoformat()
    window_root.mkdir(parents=True, exist_ok=True)

    all_raw: list[dict[str, Any]] = []
    pages_fetched = 0
    skip = 0
    expected_total: int | None = None

    while True:
        page = client.fetch_page(
            top=page_size,
            skip=skip,
            filter_expression=filter_expression,
            order_by=order_by,
            inline_count=(skip == 0),
        )

        pages_fetched += 1
        all_raw.extend(page.records)

        if expected_total is None:
            expected_total = page.total_count

        raw_path = window_root / f"page_{pages_fetched:05d}.json"
        raw_path.write_text(
            json.dumps(page.raw_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        log(
            f"  page={pages_fetched} skip={skip} "
            f"records={len(page.records)} total={page.total_count}"
        )

        if not page.records:
            break

        # The live service has been observed to cap a request such as
        # $top=100 at 50 records. Advance by the number actually returned,
        # not by the requested page size.
        skip += len(page.records)

        if expected_total is not None and skip >= expected_total:
            break

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    normalized_records: list[dict[str, Any]] = []
    rejected = 0

    for raw_record in all_raw:
        try:
            normalized_records.append(
                normalize_incident(raw_record).model_dump(mode="json")
            )
        except Exception:
            rejected += 1

    result = IngestionWindowResult(
        start_date=start_date,
        end_date=end_date,
        pages_fetched=pages_fetched,
        raw_records=len(all_raw),
        normalized_records=len(normalized_records),
        rejected_records=rejected,
    )

    return result, normalized_records
