from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSON Lines records from a UTF-8 file."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def populated_count(values: list[Any]) -> int:
    """Count non-empty values."""
    return sum(value not in (None, "", [], {}) for value in values)


def build_profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a reproducible completeness profile for the CPSC benchmark."""
    products = [
        product
        for recall in rows
        for product in (recall.get("products") or [])
    ]

    product_types = Counter(
        product.get("type")
        for product in products
        if product.get("type") not in (None, "")
    )

    product_models = Counter(
        bool(product.get("model"))
        for product in products
    )

    return {
        "recall_count": len(rows),
        "product_record_count": len(products),
        "recall_fields": {
            "description": populated_count([r.get("description") for r in rows]),
            "hazards": populated_count([r.get("hazards") for r in rows]),
            "injuries": populated_count([r.get("injuries") for r in rows]),
            "remedies": populated_count([r.get("remedies") for r in rows]),
            "retailers": populated_count([r.get("retailers") for r in rows]),
            "manufacturers": populated_count([r.get("manufacturers") for r in rows]),
            "product_upcs": populated_count([r.get("product_upcs") for r in rows]),
        },
        "product_fields": {
            "name": populated_count([p.get("name") for p in products]),
            "description": populated_count([p.get("description") for p in products]),
            "model": populated_count([p.get("model") for p in products]),
            "type": populated_count([p.get("type") for p in products]),
            "category_id": populated_count([p.get("category_id") for p in products]),
            "number_of_units": populated_count([p.get("number_of_units") for p in products]),
        },
        "product_types_non_null": dict(product_types.most_common(25)),
        "product_models_present": product_models.get(True, 0),
        "product_models_missing": product_models.get(False, 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile completeness of the historical CPSC benchmark."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/benchmark/cpsc/recalls.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmark/cpsc/profile.json"),
    )
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    profile = build_profile(rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU historical CPSC benchmark profile")
    print("------------------------------------------")
    print(f"Recalls: {profile['recall_count']}")
    print(f"Product records: {profile['product_record_count']}")
    print(
        "Product type populated: "
        f"{profile['product_fields']['type']}/{profile['product_record_count']}"
    )
    print(
        "Category ID populated: "
        f"{profile['product_fields']['category_id']}/{profile['product_record_count']}"
    )
    print(
        "Model populated: "
        f"{profile['product_fields']['model']}/{profile['product_record_count']}"
    )
    print(
        "UPC-bearing recalls: "
        f"{profile['recall_fields']['product_upcs']}/{profile['recall_count']}"
    )
    print(f"Profile: {args.output}")


if __name__ == "__main__":
    main()
