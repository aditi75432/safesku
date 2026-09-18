from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
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
    resumed_from_skip: int = 0
    reused_raw_pages: bool = False


@dataclass(frozen=True)
class RawWindowState:
    records: list[dict[str, Any]]
    expected_total: int | None
    page_count: int


def next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def iter_month_windows(
    start_date: date,
    end_date: date,
) -> list[tuple[date, date]]:
    if end_date <= start_date:
        raise ValueError("end_date must be after start_date.")

    windows: list[tuple[date, date]] = []
    cursor = date(start_date.year, start_date.month, 1)

    while cursor < end_date:
        window_end = min(next_month(cursor), end_date)
        windows.append((max(cursor, start_date), window_end))
        cursor = window_end

    return windows


def odata_datetime(value: date) -> str:
    return f"datetime'{value.isoformat()}T00:00:00'"


def build_filter(start_date: date, end_date: date) -> str:
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
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _extract_raw_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("d", payload)
    if isinstance(data, dict):
        records = data.get("results")
    else:
        records = data

    if records is None:
        records = payload.get("value")
    if records is None:
        return []
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        return []

    return [record for record in records if isinstance(record, dict)]


def _extract_total_count(payload: dict[str, Any]) -> int | None:
    data = payload.get("d", payload)
    if not isinstance(data, dict):
        return None

    raw_count = data.get("__count") or data.get("odata.count")
    if raw_count in (None, ""):
        return None

    try:
        return int(raw_count)
    except (TypeError, ValueError):
        return None


def load_raw_window(window_root: Path) -> RawWindowState:
    page_paths = sorted(window_root.glob("page_*.json"))

    records: list[dict[str, Any]] = []
    expected_total: int | None = None

    for page_path in page_paths:
        payload = json.loads(page_path.read_text(encoding="utf-8"))
        if expected_total is None:
            expected_total = _extract_total_count(payload)
        records.extend(_extract_raw_records(payload))

    return RawWindowState(
        records=records,
        expected_total=expected_total,
        page_count=len(page_paths),
    )


def normalize_records(
    raw_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    normalized_records: list[dict[str, Any]] = []
    rejected = 0

    for raw_record in raw_records:
        try:
            normalized_records.append(
                normalize_incident(raw_record).model_dump(mode="json")
            )
        except Exception:
            rejected += 1

    return normalized_records, rejected


def ingest_window(
    client: SaferProductsClient,
    *,
    start_date: date,
    end_date: date,
    raw_root: Path,
    page_size: int,
    sleep_seconds: float,
    existing_state: RawWindowState | None = None,
    log: Callable[[str], None] = print,
) -> tuple[IngestionWindowResult, list[dict[str, Any]]]:
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

    state = existing_state or RawWindowState([], None, 0)
    all_raw = list(state.records)
    expected_total = state.expected_total
    skip = len(all_raw)
    page_number = state.page_count
    resumed_from_skip = skip

    if expected_total is not None and skip >= expected_total:
        normalized, rejected = normalize_records(all_raw)
        return (
            IngestionWindowResult(
                start_date=start_date,
                end_date=end_date,
                pages_fetched=page_number,
                raw_records=len(all_raw),
                normalized_records=len(normalized),
                rejected_records=rejected,
                resumed_from_skip=resumed_from_skip,
                reused_raw_pages=True,
            ),
            normalized,
        )

    while True:
        page = client.fetch_page(
            top=page_size,
            skip=skip,
            filter_expression=filter_expression,
            order_by=order_by,
            inline_count=(skip == 0),
        )

        page_number += 1
        all_raw.extend(page.records)

        if expected_total is None:
            expected_total = page.total_count

        raw_path = window_root / f"page_{page_number:05d}.json"
        raw_path.write_text(
            json.dumps(page.raw_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        log(
            f"  page={page_number} skip={skip} "
            f"records={len(page.records)} total={page.total_count}"
        )

        if not page.records:
            break

        # The service has been observed to cap $top=100 at 50 records.
        # Always advance by the number actually returned.
        skip += len(page.records)

        if expected_total is not None and skip >= expected_total:
            break

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    normalized, rejected = normalize_records(all_raw)

    return (
        IngestionWindowResult(
            start_date=start_date,
            end_date=end_date,
            pages_fetched=page_number,
            raw_records=len(all_raw),
            normalized_records=len(normalized),
            rejected_records=rejected,
            resumed_from_skip=resumed_from_skip,
            reused_raw_pages=resumed_from_skip > 0,
        ),
        normalized,
    )


def merge_window_outputs(window_paths: list[Path]) -> list[dict[str, Any]]:
    records_by_id: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for path in window_paths:
        if not path.exists():
            continue

        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            record = json.loads(line)
            records_by_id[record["source_record_id"]] = record

    records = list(records_by_id.values())
    records.sort(
        key=lambda record: (
            record.get("incident_date") or "",
            record.get("source_record_id") or "",
        )
    )
    return records
