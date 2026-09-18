from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any


def scalar_details(details: Any) -> dict[str, str]:
    if not isinstance(details, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in details.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            result[str(key)] = str(value)
        else:
            result[str(key)] = json.dumps(value, ensure_ascii=False)
    return result


def first_nonempty(details: dict[str, str], *keys: str) -> str:
    lowered = {key.lower(): value for key, value in details.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value:
            return value
    return ""


def normalize(record: dict[str, Any], source_category: str) -> dict[str, Any]:
    details = scalar_details(record.get("details"))
    features = record.get("features") or []
    description = record.get("description") or []
    categories = record.get("categories") or []

    if not isinstance(features, list):
        features = [str(features)]
    if not isinstance(description, list):
        description = [str(description)]
    if not isinstance(categories, list):
        categories = [str(categories)]

    brand = first_nonempty(details, "Brand", "brand")
    manufacturer = first_nonempty(details, "Manufacturer", "manufacturer")
    model = first_nonempty(details, "Model", "model")
    upc = first_nonempty(details, "UPC", "UPC Code", "GTIN", "EAN")

    return {
        "source": "amazon_reviews_2023",
        "source_category": source_category,
        "parent_asin": str(record.get("parent_asin") or ""),
        "title": str(record.get("title") or ""),
        "brand": brand,
        "manufacturer": manufacturer,
        "model": model,
        "upc": upc,
        "store": str(record.get("store") or ""),
        "main_category": str(record.get("main_category") or ""),
        "categories": categories,
        "features": [str(x) for x in features],
        "description": [str(x) for x in description],
        "average_rating": record.get("average_rating"),
        "rating_number": record.get("rating_number"),
        "price": record.get("price"),
        "details": details,
    }


def process_file(path: Path, output_handle) -> tuple[int, int]:
    source_category = path.name.removeprefix("meta_").removesuffix(".jsonl.gz")
    total = 0
    normalized = 0

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            total += 1
            record = json.loads(line)
            result = normalize(record, source_category)
            if not result["parent_asin"] or not result["title"]:
                continue
            output_handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            normalized += 1

    return total, normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize Amazon Reviews'23 metadata into SafeSKU records.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/amazon/raw/metadata"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/amazon/normalized/product_metadata.jsonl"),
    )
    args = parser.parse_args()

    files = sorted(args.input_dir.glob("meta_*.jsonl.gz"))
    if not files:
        raise FileNotFoundError(f"No metadata files found in {args.input_dir}")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    normalized = 0
    with args.output.open("w", encoding="utf-8") as output_handle:
        for path in files:
            file_total, file_normalized = process_file(path, output_handle)
            total += file_total
            normalized += file_normalized
            print(f"{path.name}: {file_total:,} records -> {file_normalized:,} normalized")

    print(f"Total input records: {total:,}")
    print(f"Total normalized: {normalized:,}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
