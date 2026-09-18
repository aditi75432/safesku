from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def profile(path: Path) -> dict:
    total = 0
    with_brand = 0
    with_model = 0
    with_upc = 0
    with_manufacturer = 0
    parents = Counter()
    categories = Counter()

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            total += 1
            with_brand += bool(record.get("brand"))
            with_model += bool(record.get("model"))
            with_upc += bool(record.get("upc"))
            with_manufacturer += bool(record.get("manufacturer"))
            parents[record["parent_asin"]] += 1
            categories[record.get("source_category", "unknown")] += 1

    duplicate_parent_records = sum(count - 1 for count in parents.values() if count > 1)

    return {
        "total_rows": total,
        "unique_parent_asins": len(parents),
        "duplicate_parent_rows": duplicate_parent_records,
        "with_brand": with_brand,
        "with_model": with_model,
        "with_upc": with_upc,
        "with_manufacturer": with_manufacturer,
        "source_categories": dict(categories),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile normalized Amazon metadata.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/amazon/normalized/product_metadata.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/amazon/manifests/metadata_profile.json"),
    )
    args = parser.parse_args()

    result = profile(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("SafeSKU Amazon metadata profile")
    print("--------------------------------")
    for key, value in result.items():
        print(f"{key}: {value}")
    print(f"Profile: {args.output}")


if __name__ == "__main__":
    main()
