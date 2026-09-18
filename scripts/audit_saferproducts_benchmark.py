from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from app.services.saferproducts.normalizer import normalize_incident


def iter_raw_records(raw_root: Path) -> Iterator[tuple[Path, int, dict[str, Any]]]:
    """Yield records from raw/YYYY-MM-DD/page_XXXXX.json snapshots."""
    for path in sorted(raw_root.glob("*/*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = payload.get("d", payload)
        records = data.get("results") if isinstance(data, dict) else data

        if records is None:
            records = payload.get("value", [])

        if isinstance(records, dict):
            records = [records]

        if not isinstance(records, list):
            continue

        for index, record in enumerate(records):
            if isinstance(record, dict):
                yield path, index, record


def main() -> None:
    raw_root = Path("data/benchmark/saferproducts/raw")
    processed = Path("data/benchmark/saferproducts/incidents.jsonl")

    source_id_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    failure_examples: dict[str, dict[str, Any]] = {}

    incident_date_missing = 0
    publication_date_missing = 0
    raw_count = 0
    normalized_raw_count = 0

    for path, index, record in iter_raw_records(raw_root):
        raw_count += 1

        try:
            incident = normalize_incident(record)
            normalized_raw_count += 1
            source_id_counts[incident.source_record_id] += 1

            if incident.incident_date is None:
                incident_date_missing += 1

            if incident.publication_date is None:
                publication_date_missing += 1

        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            failure_counts[reason] += 1
            failure_examples.setdefault(
                reason,
                {
                    "file": str(path),
                    "record_index": index,
                    "IncidentReportNumber": record.get("IncidentReportNumber"),
                    "keys": sorted(record.keys()),
                },
            )

    duplicates = {
        source_id: count
        for source_id, count in source_id_counts.items()
        if count > 1
    }

    processed_count = 0
    if processed.exists():
        processed_count = sum(
            1
            for line in processed.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    report = {
        "raw_records_observed": raw_count,
        "records_normalized_from_raw": normalized_raw_count,
        "normalization_failures": sum(failure_counts.values()),
        "failure_reasons": dict(failure_counts.most_common()),
        "failure_examples": failure_examples,
        "unique_source_ids_in_successful_raw": len(source_id_counts),
        "duplicate_source_id_count": len(duplicates),
        "duplicate_source_ids_top_20": dict(
            sorted(
                duplicates.items(),
                key=lambda item: (-item[1], item[0]),
            )[:20]
        ),
        "records_missing_incident_date": incident_date_missing,
        "records_missing_publication_date": publication_date_missing,
        "processed_jsonl_count": processed_count,
    }

    output = Path("data/benchmark/saferproducts/audit.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "",
        encoding="utf-8",
    )

    print("SafeSKU SaferProducts benchmark audit")
    print("--------------------------------------")
    print(f"Raw records observed: {raw_count}")
    print(f"Normalized from raw: {normalized_raw_count}")
    print(f"Normalization failures: {report['normalization_failures']}")
    print(
        "Unique successful source IDs: "
        f"{report['unique_source_ids_in_successful_raw']}"
    )
    print(f"Duplicate source IDs: {report['duplicate_source_id_count']}")
    print(f"Missing incident date: {incident_date_missing}")
    print(f"Missing publication date: {publication_date_missing}")
    print(f"Processed JSONL records: {processed_count}")

    if failure_counts:
        print("FAILURE REASONS")
        for reason, count in failure_counts.most_common():
            print(f"{count}: {reason}")
            print(f"  Example: {failure_examples[reason]}")

    if duplicates:
        print("DUPLICATE SOURCE IDS")
        for source_id, count in sorted(
            duplicates.items(),
            key=lambda item: (-item[1], item[0]),
        )[:20]:
            print(f"{count}: {source_id}")

    print(f"Audit: {output}")


if __name__ == "__main__":
    main()
