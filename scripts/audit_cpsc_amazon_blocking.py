from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (value or "").lower()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit CPSC -> Amazon blocking behavior.")
    parser.add_argument("--cpsc", type=Path, default=Path("data/benchmark/cpsc/recalls.jsonl"))
    parser.add_argument("--candidates", type=Path, default=Path("data/benchmark/amazon_linkage/candidates.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/benchmark/amazon_linkage/blocking_audit_report.json"))
    args = parser.parse_args()

    product_tokens: dict[tuple[str, int], set[str]] = {}
    recall_names: dict[str, str] = {}

    for recall in read_jsonl(args.cpsc):
        recall_id = str(recall.get("recall_number") or recall.get("source_record_id") or "")
        products = recall.get("products") or []
        if isinstance(products, dict):
            products = [products]
        for idx, product in enumerate(products):
            if isinstance(product, dict):
                name = str(product.get("name") or "")
                product_tokens[(recall_id, idx)] = tokens(name)
                recall_names[recall_id] = name

    candidate_by_product: defaultdict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in read_jsonl(args.candidates):
        key = (
            str(row.get("cpsc_recall_number") or row.get("cpsc_source_record_id") or ""),
            int(row.get("cpsc_product_index") or 0),
        )
        candidate_by_product[key].append(row)

    rows = []
    for key, candidates in candidate_by_product.items():
        shared_counts = Counter(int(row.get("shared_product_token_count") or 0) for row in candidates)
        rows.append(
            {
                "recall": key[0],
                "product_index": key[1],
                "product_name": recall_names.get(key[0], ""),
                "candidate_count": len(candidates),
                "shared_token_histogram": dict(sorted(shared_counts.items())),
                "max_shared_tokens": max(shared_counts) if shared_counts else 0,
            }
        )

    rows.sort(key=lambda row: row["candidate_count"], reverse=True)

    report = {
        "products_with_candidates": len(rows),
        "candidate_rows": sum(row["candidate_count"] for row in rows),
        "top_candidate_products": rows[:25],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("SafeSKU CPSC -> Amazon blocking audit")
    print("-------------------------------------")
    print(f"Products with candidates: {report['products_with_candidates']}")
    print(f"Candidate rows: {report['candidate_rows']}")
    print()
    for row in rows[:15]:
        print(
            f"{row['recall']} | {row['candidate_count']} candidates | "
            f"{row['product_name'][:100]}"
        )
    print()
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
