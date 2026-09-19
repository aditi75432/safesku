from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Any
from collections import Counter

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


def collect_cpsc_upcs(recall: dict[str, Any], product: dict[str, Any]) -> list[str]:
    values = string_list(recall.get("product_upcs"))
    for key in ("upc", "UPC"):
        if product.get(key):
            values.append(str(product[key]))
    return values


def generate_candidates(product: dict[str, Any], recall: dict[str, Any], index: dict[str, Any]):
    name_tokens = set(tokenize(product.get("name") or ""))

    exact_parents = set()
    for value in collect_cpsc_upcs(recall, product):
        normalized = "".join(ch for ch in str(value) if ch.isdigit())
        if normalized:
            exact_parents.update(index["exact_upc_index"].get(normalized, []))

    # Discovery uses category-local rare-token postings. Full Amazon titles are
    # checked afterward so the second shared token may be common.
    rare_seed_parents: set[str] = set()
    for token in name_tokens:
        rare_seed_parents.update(index["rare_postings"].get(token, []))

    lexical_parents: set[str] = set()
    for parent in rare_seed_parents:
        amazon = index["amazon_products"].get(parent)
        if not amazon:
            continue
        amazon_tokens = set(tokenize(amazon.get("title") or ""))
        if len(name_tokens & amazon_tokens) >= index["blocker"]["min_shared_tokens"]:
            lexical_parents.add(parent)

    return exact_parents, lexical_parents, name_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CPSC -> Amazon candidates from a category-aware index.")
    parser.add_argument("--cpsc-input", type=Path, default=Path("data/benchmark/cpsc/recalls.jsonl"))
    parser.add_argument("--index", type=Path, default=Path("data/benchmark/amazon_linkage/amazon_cpsc_index.pkl"))
    parser.add_argument("--output", type=Path, default=Path("data/benchmark/amazon_linkage/candidates.jsonl"))
    args = parser.parse_args()

    with args.index.open("rb") as handle:
        index = pickle.load(handle)
    if index.get("version") != 2:
        raise ValueError("Incompatible Amazon index. Rebuild with build_amazon_cpsc_index.py.")

    products = index["amazon_products"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "index_version": index["version"],
        "policy": index["blocker"],
        "cpsc_records": 0,
        "cpsc_product_mentions": 0,
        "amazon_parent_asins_indexed": len(products),
        "product_mentions_with_candidates": 0,
        "candidate_pairs": 0,
        "exact_upc_candidates": 0,
        "lexical_candidates": 0,
        "candidate_pairs_written": 0,
    }

    with args.output.open("w", encoding="utf-8") as out:
        for recall in read_jsonl(args.cpsc_input):
            manifest["cpsc_records"] += 1
            for product_index, product in enumerate(product_mentions(recall)):
                manifest["cpsc_product_mentions"] += 1
                exact_parents, lexical_parents, name_tokens = generate_candidates(product, recall, index)
                parents = exact_parents | lexical_parents
                if parents:
                    manifest["product_mentions_with_candidates"] += 1
                manifest["candidate_pairs"] += len(parents)
                manifest["exact_upc_candidates"] += len(exact_parents)
                manifest["lexical_candidates"] += len(lexical_parents)

                rows = []
                for parent in parents:
                    amazon = products.get(parent)
                    if not amazon:
                        continue
                    amazon_tokens = set(tokenize(amazon.get("title") or ""))
                    rows.append({
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
                        "blocking_sources": ((["exact_upc"] if parent in exact_parents else []) + (["two_tokens_plus_category_rare_token"] if parent in lexical_parents else [])),
                        "exact_upc": exact_upc(collect_cpsc_upcs(recall, product), amazon.get("upc")),
                        "shared_product_token_count": len(name_tokens & amazon_tokens),
                        "product_token_jaccard": jaccard(name_tokens, amazon_tokens),
                    })

                rows.sort(key=lambda row: (-row["exact_upc"], -row["shared_product_token_count"], -row["product_token_jaccard"], row["amazon_parent_asin"]))
                for row in rows:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    manifest["candidate_pairs_written"] += 1

    manifest["complete_candidate_set"] = True
    manifest_path = args.output.parent / "candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("SafeSKU CPSC -> Amazon candidate generation")
    print("--------------------------------------------")
    print(f"CPSC recalls: {manifest['cpsc_records']}")
    print(f"CPSC product mentions: {manifest['cpsc_product_mentions']}")
    print(f"Amazon products indexed: {manifest['amazon_parent_asins_indexed']}")
    print(f"Product mentions with candidates: {manifest['product_mentions_with_candidates']}")
    print(f"Candidate pairs: {manifest['candidate_pairs']}")
    print(f"Exact UPC candidates: {manifest['exact_upc_candidates']}")
    print(f"Lexical candidates: {manifest['lexical_candidates']}")
    print(f"Candidate pairs written: {manifest['candidate_pairs_written']}")
    print(f"Candidates: {args.output}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
