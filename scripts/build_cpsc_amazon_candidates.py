from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.linkage.amazon_features import exact_upc, jaccard, tokenize


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def product_mentions(recall: dict[str, Any]) -> list[dict[str, Any]]:
    products = recall.get("products") or []
    if isinstance(products, dict):
        products = [products]
    return [p for p in products if isinstance(p, dict)]


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result = []
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


def build_indices(amazon_path: Path):
    rows = []
    upc_index: dict[str, set[str]] = defaultdict(set)
    token_index: dict[str, set[str]] = defaultdict(set)

    for row in read_jsonl(amazon_path):
        parent = str(row.get("parent_asin") or "").strip()
        title = str(row.get("title") or "").strip()
        if not parent or not title:
            continue

        row["_title_tokens"] = set(tokenize(title))
        rows.append(row)

        upc = re.sub(r"\D", "", str(row.get("upc") or ""))
        if upc:
            upc_index[upc].add(parent)

        for token in row["_title_tokens"]:
            token_index[token].add(parent)

    by_parent = {row["parent_asin"]: row for row in rows}
    return by_parent, upc_index, token_index


def collect_cpsc_upcs(recall: dict[str, Any], product: dict[str, Any]) -> list[str]:
    values = list(string_list(recall.get("product_upcs")))
    for key in ("upc", "UPC"):
        if product.get(key):
            values.append(str(product[key]))
    return values


def generate_candidates(
    product: dict[str, Any],
    recall: dict[str, Any],
    upc_index: dict[str, set[str]],
    token_index: dict[str, set[str]],
    max_token_document_frequency: int = 250,
    min_shared_tokens: int = 2,
):
    if max_token_document_frequency < 1:
        raise ValueError("max_token_document_frequency must be >= 1")
    if min_shared_tokens < 1:
        raise ValueError("min_shared_tokens must be >= 1")

    cpsc_upcs = collect_cpsc_upcs(recall, product)

    exact = set()
    for value in cpsc_upcs:
        digits = re.sub(r"\D", "", value)
        if digits:
            exact.update(upc_index.get(digits, set()))

    name_tokens = set(tokenize(product.get("name") or ""))

    # Candidate generation uses rarity-aware lexical blocking:
    # at least N shared CPSC product-name tokens, and at least one shared token
    # must occur in no more than max_token_document_frequency Amazon titles.
    # This suppresses generic marketplace terms such as "baby" and "products".
    token_counts: Counter[str] = Counter()
    rare_hit: set[str] = set()

    for token in name_tokens:
        postings = token_index.get(token)
        if not postings:
            continue
        document_frequency = len(postings)
        for parent in postings:
            token_counts[parent] += 1
        if document_frequency <= max_token_document_frequency:
            rare_hit.update(postings)

    lexical = {
        parent
        for parent, count in token_counts.items()
        if count >= min_shared_tokens and parent in rare_hit
    }

    return exact, lexical, name_tokens, cpsc_upcs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CPSC -> Amazon product candidates.")
    parser.add_argument("--cpsc-input", type=Path, default=Path("data/benchmark/cpsc/recalls.jsonl"))
    parser.add_argument("--amazon-input", type=Path, default=Path("data/amazon/normalized/product_metadata.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/benchmark/amazon_linkage/candidates.jsonl"))
    parser.add_argument("--max-token-document-frequency", type=int, default=250)
    parser.add_argument("--min-shared-tokens", type=int, default=2)
    args = parser.parse_args()

    by_parent, upc_index, token_index = build_indices(args.amazon_input)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "policy": "exact_upc OR min_shared_tokens_with_at_least_one_rare_token",
        "max_token_document_frequency": args.max_token_document_frequency,
        "min_shared_tokens": args.min_shared_tokens,
        "cpsc_records": 0,
        "cpsc_product_mentions": 0,
        "amazon_parent_asins": len(by_parent),
        "product_mentions_with_candidates": 0,
        "candidate_pairs": 0,
        "exact_upc_candidates": 0,
        "lexical_candidates": 0,
        "candidate_pairs_written": 0,
        "candidate_count_by_product": [],
    }

    with args.output.open("w", encoding="utf-8") as out:
        for recall in read_jsonl(args.cpsc_input):
            manifest["cpsc_records"] += 1
            mentions = product_mentions(recall)

            for product_index, product in enumerate(mentions):
                manifest["cpsc_product_mentions"] += 1

                exact, lexical, name_tokens, cpsc_upcs = generate_candidates(
                    product,
                    recall,
                    upc_index,
                    token_index,
                    max_token_document_frequency=args.max_token_document_frequency,
                    min_shared_tokens=args.min_shared_tokens,
                )
                parents = exact | lexical

                if parents:
                    manifest["product_mentions_with_candidates"] += 1

                manifest["candidate_pairs"] += len(parents)
                manifest["exact_upc_candidates"] += len(exact)
                manifest["lexical_candidates"] += len(lexical)

                rows = []
                for parent in parents:
                    amazon = by_parent[parent]
                    rows.append(
                        {
                            "cpsc_source_record_id": recall.get("source_record_id"),
                            "cpsc_recall_number": recall.get("recall_number"),
                            "cpsc_recall_date": recall.get("recall_date"),
                            "cpsc_product_index": product_index,
                            "cpsc_product_name": product.get("name") or "",
                            "amazon_parent_asin": parent,
                            "amazon_title": amazon.get("title") or "",
                            "amazon_brand": amazon.get("brand") or "",
                            "amazon_manufacturer": amazon.get("manufacturer") or "",
                            "amazon_model": amazon.get("model") or "",
                            "amazon_upc": amazon.get("upc") or "",
                            "amazon_category": amazon.get("main_category") or amazon.get("source_category") or "",
                            "blocking_sources": (
                                (["exact_upc"] if parent in exact else [])
                                + (["two_tokens_plus_rare_token"] if parent in lexical else [])
                            ),
                            "exact_upc": exact_upc(cpsc_upcs, amazon.get("upc")),
                            "shared_product_token_count": len(name_tokens & amazon["_title_tokens"]),
                            "product_token_jaccard": jaccard(name_tokens, amazon["_title_tokens"]),
                        }
                    )

                rows.sort(
                    key=lambda row: (
                        -row["exact_upc"],
                        -row["shared_product_token_count"],
                        -row["product_token_jaccard"],
                        row["amazon_parent_asin"],
                    )
                )

                manifest["candidate_count_by_product"].append(
                    {
                        "recall_number": recall.get("recall_number"),
                        "cpsc_product_index": product_index,
                        "count": len(rows),
                    }
                )

                for row in rows:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                manifest["candidate_pairs_written"] += len(rows)

    manifest["complete_candidate_set"] = True
    (args.output.parent / "candidate_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print("SafeSKU CPSC -> Amazon candidate generation")
    print("--------------------------------------------")
    print(f"CPSC recalls: {manifest['cpsc_records']}")
    print(f"CPSC product mentions: {manifest['cpsc_product_mentions']}")
    print(f"Amazon parent ASINs: {manifest['amazon_parent_asins']}")
    print(f"Product mentions with candidates: {manifest['product_mentions_with_candidates']}")
    print(f"Candidate pairs: {manifest['candidate_pairs']}")
    print(f"Exact UPC candidates: {manifest['exact_upc_candidates']}")
    print(f"Lexical candidates: {manifest['lexical_candidates']}")
    print(f"Candidate pairs written: {manifest['candidate_pairs_written']}")
    print(f"Rarity threshold: {manifest['max_token_document_frequency']}")
    print(f"Minimum shared tokens: {manifest['min_shared_tokens']}")
    print(f"Candidates: {args.output}")
    print(f"Manifest: {args.output.parent / 'candidate_manifest.json'}")


if __name__ == "__main__":
    main()
