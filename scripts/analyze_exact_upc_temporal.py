from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def classify_temporal_status(row: dict[str, Any]) -> str:
    recall_date = parse_date(row.get("cpsc_recall_date"))
    incident_date = parse_date(row.get("incident_date"))
    publication_date = parse_date(row.get("publication_date"))

    if recall_date is None or incident_date is None or publication_date is None:
        return "insufficient_dates"

    if incident_date < recall_date and publication_date < recall_date:
        return "pre_recall_public"

    if incident_date < recall_date and publication_date >= recall_date:
        return "pre_incident_published_after_recall"

    if incident_date >= recall_date:
        return "incident_on_or_after_recall"

    return "insufficient_dates"


def main() -> None:
    input_path = Path("data/benchmark/linkage/exact_upc_review.jsonl")
    output_path = Path("data/benchmark/linkage/exact_upc_temporal_audit.json")

    rows = load_jsonl(input_path)
    status_counts = Counter(classify_temporal_status(row) for row in rows)

    recalls_by_status: defaultdict[str, set[str]] = defaultdict(set)
    for row in rows:
        recalls_by_status[classify_temporal_status(row)].add(
            str(row["cpsc_source_record_id"])
        )

    qualifying_rows = [
        row
        for row in rows
        if classify_temporal_status(row) == "pre_recall_public"
    ]

    report = {
        "pair_count": len(rows),
        "linked_recall_count": len(
            {row["cpsc_source_record_id"] for row in rows}
        ),
        "pair_status_counts": dict(status_counts),
        "recall_counts_by_status": {
            status: len(ids)
            for status, ids in sorted(recalls_by_status.items())
        },
        "pre_recall_public_pairs": qualifying_rows,
        "pre_recall_public_recall_ids": sorted(
            {row["cpsc_source_record_id"] for row in qualifying_rows}
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU exact-UPC temporal audit")
    print("--------------------------------")
    print(f"UPC-linked pairs: {report['pair_count']}")
    print(f"UPC-linked recalls: {report['linked_recall_count']}")

    print("\nPAIR STATUS")
    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")

    print("\nRECALLS BY STATUS")
    for status, ids in sorted(recalls_by_status.items()):
        print(f"{status}: {len(ids)}")

    print("\nPRE-RECALL PUBLIC PAIRS")
    for row in qualifying_rows:
        print(
            f"{row['cpsc_recall_number']} | "
            f"{row['cpsc_recall_date']} | "
            f"incident={row['incident_date']} | "
            f"published={row['publication_date']} | "
            f"{row['cpsc_product_name']} | "
            f"{row['saferproducts_source_record_id']}"
        )

    print(f"\nAudit: {output_path}")


if __name__ == "__main__":
    main()
