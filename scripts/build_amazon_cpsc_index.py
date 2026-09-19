from __future__ import annotations

import argparse
import json
import pickle
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.linkage.amazon_features import tokenize

MAX_RARE_DOCUMENT_FREQUENCY = 250
POSTING_CAP = MAX_RARE_DOCUMENT_FREQUENCY + 1
PROGRESS_EVERY = 250_000


def read_jsonl(path: Path):
    try:
        import orjson  # type: ignore
    except ImportError:
        orjson = None

    with path.open("rb") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield orjson.loads(line) if orjson is not None else json.loads(line)


def product_mentions(recall: dict[str, Any]) -> list[dict[str, Any]]:
    products = recall.get("products") or []
    if isinstance(products, dict):
        products = [products]
    return [item for item in products if isinstance(item, dict)]


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                for key in ("upc", "UPC", "value", "code"):
                    if item.get(key):
                        result.append(str(item[key]))
                        break
        return result
    return []


def digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def load_cpsc_query(cpsc_path: Path) -> tuple[set[str], set[str], int]:
    query_tokens: set[str] = set()
    cpsc_upcs: set[str] = set()
    recalls = 0

    for recall in read_jsonl(cpsc_path):
        recalls += 1
        recall_upcs = string_list(recall.get("product_upcs"))

        for product in product_mentions(recall):
            query_tokens.update(tokenize(str(product.get("name") or "")))
            for key in ("upc", "UPC"):
                if product.get(key):
                    recall_upcs.append(str(product[key]))

        for value in recall_upcs:
            normalized = digits(value)
            if normalized:
                cpsc_upcs.add(normalized)

    return query_tokens, cpsc_upcs, recalls


def build_index(cpsc_path: Path, amazon_path: Path) -> dict[str, Any]:
    query_tokens, cpsc_upcs, recall_count = load_cpsc_query(cpsc_path)

    # Rarity is scoped to each Amazon source category. This avoids making a
    # token useless just because it is common somewhere else in the catalog.
    category_document_frequency: dict[str, Counter[str]] = defaultdict(Counter)
    category_postings: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    product_records: dict[str, dict[str, Any]] = {}

    rows = 0
    started = time.perf_counter()

    for row in read_jsonl(amazon_path):
        rows += 1
        parent = str(row.get("parent_asin") or "").strip()
        title = str(row.get("title") or "").strip()
        if not parent or not title:
            continue

        category = (
            str(row.get("source_category") or "").strip()
            or str(row.get("main_category") or "").strip()
            or "unknown"
        )

        title_tokens = set(tokenize(title))
        relevant_tokens = title_tokens & query_tokens

        for token in relevant_tokens:
            category_document_frequency[category][token] += 1
            postings = category_postings[category][token]
            if len(postings) < POSTING_CAP:
                postings.append(parent)

        amazon_upc = digits(str(row.get("upc") or ""))
        exact_identifier = bool(amazon_upc and amazon_upc in cpsc_upcs)

        if relevant_tokens or exact_identifier:
            product_records[parent] = {
                "parent_asin": parent,
                "title": title,
                "brand": row.get("brand") or "",
                "manufacturer": row.get("manufacturer") or "",
                "model": row.get("model") or "",
                "upc": row.get("upc") or "",
                "main_category": row.get("main_category") or "",
                "source_category": row.get("source_category") or "",
            }

        if rows % PROGRESS_EVERY == 0:
            elapsed = time.perf_counter() - started
            rate = rows / elapsed if elapsed else 0
            print(
                f"Indexed {rows:,} Amazon products | {rate:,.0f} rows/s | "
                f"categories={len(category_document_frequency)}"
            )

    # Keep only token/category pairs that are rare within that category.
    rare_postings: dict[str, set[str]] = defaultdict(set)
    rare_token_category_pairs = 0

    for category, token_counts in category_document_frequency.items():
        for token, df in token_counts.items():
            if df <= MAX_RARE_DOCUMENT_FREQUENCY:
                rare_token_category_pairs += 1
                rare_postings[token].update(category_postings[category][token])

    exact_upc_index: dict[str, list[str]] = defaultdict(list)
    for parent, row in product_records.items():
        amazon_upc = digits(str(row.get("upc") or ""))
        if amazon_upc and amazon_upc in cpsc_upcs:
            exact_upc_index[amazon_upc].append(parent)

    retained_parents = set()
    for parents in rare_postings.values():
        retained_parents.update(parents)
    for parents in exact_upc_index.values():
        retained_parents.update(parents)

    filtered_products = {
        parent: product_records[parent]
        for parent in retained_parents
        if parent in product_records
    }

    return {
        "version": 2,
        "blocker": {
            "type": "exact_upc_or_two_shared_tokens_with_one_category_rare_token",
            "max_token_document_frequency": MAX_RARE_DOCUMENT_FREQUENCY,
            "min_shared_tokens": 2,
            "rarity_scope": "amazon_source_category",
        },
        "cpsc_recalls": recall_count,
        "cpsc_query_tokens": query_tokens,
        "cpsc_upcs": cpsc_upcs,
        "amazon_rows_scanned": rows,
        "amazon_categories": sorted(category_document_frequency),
        "rare_token_count": len(rare_postings),
        "rare_token_category_pairs": rare_token_category_pairs,
        "rare_postings": {token: sorted(parents) for token, parents in rare_postings.items()},
        "exact_upc_index": dict(exact_upc_index),
        "amazon_products": filtered_products,
        "build_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build category-aware CPSC/Amazon lexical index.")
    parser.add_argument("--cpsc-input", type=Path, default=Path("data/benchmark/cpsc/recalls.jsonl"))
    parser.add_argument("--amazon-input", type=Path, default=Path("data/amazon/normalized/product_metadata.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/benchmark/amazon_linkage/amazon_cpsc_index.pkl"))
    args = parser.parse_args()

    if not args.cpsc_input.exists():
        raise FileNotFoundError(args.cpsc_input)
    if not args.amazon_input.exists():
        raise FileNotFoundError(args.amazon_input)

    print("SafeSKU category-aware Amazon index")
    print("------------------------------------")
    print("The current Amazon corpus is scanned once.")
    print(f"Category-local rare-token DF threshold: {MAX_RARE_DOCUMENT_FREQUENCY}")
    print("Progress is printed every 250,000 rows.")
    print()

    index = build_index(args.cpsc_input, args.amazon_input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as handle:
        pickle.dump(index, handle, protocol=pickle.HIGHEST_PROTOCOL)

    print()
    print(f"Amazon rows scanned: {index['amazon_rows_scanned']:,}")
    print(f"CPSC query tokens: {len(index['cpsc_query_tokens']):,}")
    print(f"Amazon categories: {len(index['amazon_categories'])}")
    print(f"Rare token/category pairs: {index['rare_token_category_pairs']:,}")
    print(f"Rare tokens retained: {index['rare_token_count']:,}")
    print(f"Retained Amazon products: {len(index['amazon_products']):,}")
    print(f"Exact UPC postings: {sum(len(v) for v in index['exact_upc_index'].values()):,}")
    print(f"Index build seconds: {index['build_seconds']}")
    print(f"Index: {args.output}")


if __name__ == "__main__":
    main()
