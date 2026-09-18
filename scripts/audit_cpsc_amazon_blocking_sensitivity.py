from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def tokenize(value: str | None) -> set[str]:
    text = (value or "").lower()
    raw = re.findall(r"[a-z0-9]+", text)
    stopwords = {
        "a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or",
        "the", "to", "with", "this", "that", "new", "pack", "set", "model",
        "item", "product", "black", "white", "inch", "inches",
    }
    return {token for token in raw if token not in stopwords and len(token) >= 2}


def product_mentions(recall: dict[str, Any]) -> list[dict[str, Any]]:
    products = recall.get("products") or []
    if isinstance(products, dict):
        products = [products]
    return [p for p in products if isinstance(p, dict)]


def build_amazon_token_index(path: Path):
    token_index: dict[str, set[str]] = defaultdict(set)
    total_products = 0

    for row in read_jsonl(path):
        parent = str(row.get("parent_asin") or "").strip()
        title = str(row.get("title") or "").strip()
        if not parent or not title:
            continue
        total_products += 1
        for token in tokenize(title):
            token_index[token].add(parent)

    return token_index, total_products


def candidate_counts_for_product(name: str, token_index, threshold: int) -> set[str]:
    name_tokens = tokenize(name)
    usable = [
        token for token in name_tokens
        if token in token_index and len(token_index[token]) <= threshold
    ]

    # We require two shared product-name tokens, but at least one of those
    # shared tokens must be rare in the Amazon corpus. This keeps a distinctive
    # product term while avoiding generic pairs like "baby" + "product".
    counts: Counter[str] = Counter()
    rare_hit: set[str] = set()

    for token in name_tokens:
        postings = token_index.get(token)
        if not postings:
            continue
        df = len(postings)
        for parent in postings:
            counts[parent] += 1
            if df <= threshold:
                rare_hit.add(parent)

    return {
        parent
        for parent, count in counts.items()
        if count >= 2 and parent in rare_hit
    }


def summarize(values: list[int]) -> dict[str, int]:
    if not values:
        return {"min": 0, "median": 0, "p90": 0, "max": 0}
    ordered = sorted(values)

    def pct(p: float) -> int:
        index = min(len(ordered) - 1, round((len(ordered) - 1) * p))
        return ordered[index]

    return {
        "min": ordered[0],
        "median": int(median(ordered)),
        "p90": pct(0.90),
        "max": ordered[-1],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure CPSC -> Amazon blocker sensitivity across rarity thresholds."
    )
    parser.add_argument(
        "--cpsc",
        type=Path,
        default=Path("data/benchmark/cpsc/recalls.jsonl"),
    )
    parser.add_argument(
        "--amazon",
        type=Path,
        default=Path("data/amazon/normalized/product_metadata.jsonl"),
    )
    parser.add_argument(
        "--thresholds",
        type=int,
        nargs="+",
        default=[50, 100, 250, 500, 1000, 2500, 5000, 10000],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmark/amazon_linkage/blocking_sensitivity_report.json"),
    )
    args = parser.parse_args()

    token_index, amazon_products = build_amazon_token_index(args.amazon)

    results = []
    for threshold in args.thresholds:
        per_product = []
        recalls_with_candidates: set[str] = set()
        total_pairs = 0
        large_products = []

        for recall in read_jsonl(args.cpsc):
            recall_id = str(recall.get("recall_number") or recall.get("source_record_id") or "")
            for idx, product in enumerate(product_mentions(recall)):
                candidates = candidate_counts_for_product(
                    str(product.get("name") or ""),
                    token_index,
                    threshold,
                )
                count = len(candidates)
                per_product.append(count)
                total_pairs += count
                if count:
                    recalls_with_candidates.add(recall_id)
                if count >= 500:
                    large_products.append(
                        {
                            "recall": recall_id,
                            "product_index": idx,
                            "product_name": str(product.get("name") or ""),
                            "candidate_count": count,
                        }
                    )

        results.append(
            {
                "max_token_document_frequency": threshold,
                "recalls_with_candidates": len(recalls_with_candidates),
                "candidate_pairs": total_pairs,
                "candidate_count_distribution": summarize(per_product),
                "products_with_500_or_more_candidates": sorted(
                    large_products,
                    key=lambda item: item["candidate_count"],
                    reverse=True,
                )[:10],
            }
        )

    report = {
        "amazon_products": amazon_products,
        "token_count": len(token_index),
        "policy": (
            "two_or_more_shared_product_name_tokens AND at_least_one_shared_token "
            "has Amazon document frequency <= threshold"
        ),
        "thresholds": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("SafeSKU CPSC -> Amazon blocking sensitivity")
    print("--------------------------------------------")
    print(f"Amazon products: {amazon_products}")
    print(f"Distinct tokens: {len(token_index)}")
    print()
    for result in results:
        dist = result["candidate_count_distribution"]
        print(
            f"threshold={result['max_token_document_frequency']}: "
            f"recalls={result['recalls_with_candidates']} "
            f"pairs={result['candidate_pairs']} "
            f"median={dist['median']} "
            f"p90={dist['p90']} "
            f"max={dist['max']}"
        )
    print()
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
