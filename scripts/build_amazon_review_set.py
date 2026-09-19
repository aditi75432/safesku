from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_SAMPLE_SIZE = 200
DEFAULT_SEED = 20260919


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def similarity_band(row: dict[str, Any]) -> str:
    value = as_float(row.get("product_token_jaccard"))
    if value < 0.20:
        return "low"
    if value < 0.50:
        return "medium"
    return "high"


def model_band(row: dict[str, Any]) -> str:
    return "with_model" if str(row.get("amazon_model") or "").strip() else "without_model"


def brand_relation(row: dict[str, Any]) -> str:
    title = str(row.get("cpsc_product_name") or "").lower()
    brand = str(row.get("amazon_brand") or "").strip().lower()
    if not brand:
        return "brand_missing"
    return "brand_in_cpsc_name" if brand in title else "brand_not_in_cpsc_name"


def candidate_size_band(count: int) -> str:
    if count <= 5:
        return "small_bucket"
    if count <= 50:
        return "medium_bucket"
    return "large_bucket"


def build_rows(path: Path) -> list[dict[str, Any]]:
    rows = list(read_jsonl(path))
    if not rows:
        raise ValueError(f"No candidate rows found in {path}")

    counts: dict[tuple[str, int], int] = defaultdict(int)
    for row in rows:
        key = (
            str(row.get("cpsc_recall_number") or row.get("cpsc_source_record_id") or ""),
            as_int(row.get("cpsc_product_index")),
        )
        counts[key] += 1

    for row in rows:
        key = (
            str(row.get("cpsc_recall_number") or row.get("cpsc_source_record_id") or ""),
            as_int(row.get("cpsc_product_index")),
        )
        row["_candidate_count_for_product"] = counts[key]
        row["_similarity_band"] = similarity_band(row)
        row["_model_band"] = model_band(row)
        row["_brand_relation"] = brand_relation(row)
        row["_bucket_band"] = candidate_size_band(counts[key])
        row["_upc_seed"] = bool(as_int(row.get("exact_upc")))
    return rows


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("cpsc_recall_number") or row.get("cpsc_source_record_id") or ""),
        str(row.get("amazon_parent_asin") or ""),
    )


def stratified_sample(rows: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    if sample_size < 20:
        raise ValueError("sample_size must be at least 20")
    if sample_size > len(rows):
        raise ValueError(f"sample_size {sample_size} exceeds {len(rows)} candidates")

    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    selected_ids: set[tuple[str, str]] = set()

    # Keep every exact-UPC candidate. There are very few, and these provide
    # high-confidence identity anchors for the review set.
    for row in rows:
        if row["_upc_seed"] and row_key(row) not in selected_ids:
            selected.append(row)
            selected_ids.add(row_key(row))

    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = "|".join(
            (
                row["_similarity_band"],
                row["_model_band"],
                row["_brand_relation"],
                row["_bucket_band"],
            )
        )
        strata[key].append(row)

    for group in strata.values():
        rng.shuffle(group)

    remaining = sample_size - len(selected)

    # First guarantee broad coverage across distinct strata.
    names = list(strata)
    rng.shuffle(names)
    for name in names:
        if remaining <= 0:
            break
        candidates = [r for r in strata[name] if row_key(r) not in selected_ids]
        if candidates:
            row = candidates[0]
            selected.append(row)
            selected_ids.add(row_key(row))
            remaining -= 1

    # Fill the rest using round-robin across strata. Within a stratum, prefer
    # higher-similarity and larger buckets because they are harder cases.
    while remaining > 0:
        progress = False
        names = list(strata)
        rng.shuffle(names)

        for name in names:
            candidates = [r for r in strata[name] if row_key(r) not in selected_ids]
            if not candidates:
                continue

            candidates.sort(
                key=lambda r: (
                    as_float(r.get("product_token_jaccard")),
                    as_int(r.get("_candidate_count_for_product")),
                ),
                reverse=True,
            )
            row = rng.choice(candidates[: min(10, len(candidates))])
            selected.append(row)
            selected_ids.add(row_key(row))
            remaining -= 1
            progress = True

            if remaining <= 0:
                break

        if not progress:
            break

    selected.sort(
        key=lambda r: (
            str(r.get("cpsc_recall_number") or r.get("cpsc_source_record_id") or ""),
            str(r.get("amazon_parent_asin") or ""),
        )
    )
    return selected[:sample_size]


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "review_id",
        "cpsc_recall_number",
        "cpsc_recall_date",
        "cpsc_product_name",
        "amazon_parent_asin",
        "amazon_title",
        "amazon_brand",
        "amazon_manufacturer",
        "amazon_model",
        "amazon_upc",
        "amazon_category",
        "blocking_sources",
        "exact_upc",
        "shared_product_token_count",
        "product_token_jaccard",
        "similarity_band",
        "model_band",
        "brand_relation",
        "candidate_bucket_size",
        "review_label",
        "reviewer_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for number, row in enumerate(rows, start=1):
            writer.writerow(
                {
                    "review_id": f"AMZ-ER-{number:04d}",
                    "cpsc_recall_number": row.get("cpsc_recall_number", ""),
                    "cpsc_recall_date": row.get("cpsc_recall_date", ""),
                    "cpsc_product_name": row.get("cpsc_product_name", ""),
                    "amazon_parent_asin": row.get("amazon_parent_asin", ""),
                    "amazon_title": row.get("amazon_title", ""),
                    "amazon_brand": row.get("amazon_brand", ""),
                    "amazon_manufacturer": row.get("amazon_manufacturer", ""),
                    "amazon_model": row.get("amazon_model", ""),
                    "amazon_upc": row.get("amazon_upc", ""),
                    "amazon_category": row.get("amazon_category", ""),
                    "blocking_sources": json.dumps(row.get("blocking_sources", [])),
                    "exact_upc": row.get("exact_upc", 0),
                    "shared_product_token_count": row.get("shared_product_token_count", 0),
                    "product_token_jaccard": row.get("product_token_jaccard", 0),
                    "similarity_band": row["_similarity_band"],
                    "model_band": row["_model_band"],
                    "brand_relation": row["_brand_relation"],
                    "candidate_bucket_size": row["_candidate_count_for_product"],
                    "review_label": "",
                    "reviewer_notes": "",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a stratified CPSC -> Amazon product linkage review set.")
    parser.add_argument("--input", type=Path, default=Path("data/benchmark/amazon_linkage/candidates.jsonl"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/benchmark/amazon_linkage"))
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    rows = build_rows(args.input)
    selected = stratified_sample(rows, args.sample_size, args.seed)

    output_csv = args.output_dir / "amazon_human_review_set.csv"
    output_manifest = args.output_dir / "amazon_human_review_set_manifest.json"

    write_csv(selected, output_csv)

    manifest = {
        "input_candidate_rows": len(rows),
        "selected_rows": len(selected),
        "seed": args.seed,
        "requested_sample_size": args.sample_size,
        "exact_upc_rows": sum(row["_upc_seed"] for row in selected),
        "unique_recalls": len({
            str(row.get("cpsc_recall_number") or row.get("cpsc_source_record_id") or "")
            for row in selected
        }),
        "similarity_distribution": {
            band: sum(row["_similarity_band"] == band for row in selected)
            for band in ("low", "medium", "high")
        },
        "model_distribution": {
            band: sum(row["_model_band"] == band for row in selected)
            for band in ("with_model", "without_model")
        },
        "bucket_distribution": {
            band: sum(row["_bucket_band"] == band for row in selected)
            for band in ("small_bucket", "medium_bucket", "large_bucket")
        },
        "policy": (
            "Retain all exact-UPC candidates, then stratify remaining rows across "
            "lexical similarity, model availability, brand relation, and candidate "
            "bucket size. This is an identity-review sample, not a safety classifier."
        ),
        "allowed_labels": ["MATCH", "NON_MATCH", "UNCERTAIN"],
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("SafeSKU Amazon product-linkage review set")
    print("-----------------------------------------")
    print(f"Input candidate rows: {len(rows)}")
    print(f"Selected rows: {len(selected)}")
    print(f"Exact UPC candidates retained: {manifest['exact_upc_rows']}")
    print(f"Unique recalls represented: {manifest['unique_recalls']}")
    print(f"Similarity: {manifest['similarity_distribution']}")
    print(f"Model: {manifest['model_distribution']}")
    print(f"Candidate buckets: {manifest['bucket_distribution']}")
    print(f"CSV: {output_csv}")
    print(f"Manifest: {output_manifest}")


if __name__ == "__main__":
    main()
