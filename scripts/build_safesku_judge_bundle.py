#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.workspace.bundle import build_manifest, sha256_file  # noqa: E402

CPSC = ROOT / "data" / "benchmark" / "cpsc" / "recalls.jsonl"
SAFER = ROOT / "data" / "benchmark" / "saferproducts" / "incidents.jsonl"
LINKAGE = ROOT / "data" / "benchmark" / "amazon_linkage" / "candidates.jsonl"
AMAZON_PRODUCTS = ROOT / "data" / "amazon" / "normalized" / "product_metadata.jsonl"
DEFAULT_SLICE = ROOT / "data" / "runtime" / "judge_bundle" / "amazon_products_for_candidates.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "bundles" / "safesku-judge-bundle.zip"


def _jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if isinstance(obj, dict):
                yield obj


def _asin_set(path: Path) -> set[str]:
    asins: set[str] = set()
    for row in _jsonl(path):
        value = str(row.get("amazon_parent_asin") or row.get("parent_asin") or "").strip().upper()
        if value:
            asins.add(value)
    return asins


def build_product_slice(source: Path, candidate_file: Path, output: Path) -> tuple[int, int]:
    """Extract only Amazon products referenced by the SafeSKU linkage benchmark.

    We intentionally stream the 15 GB normalized catalog. The resulting slice is
    usually two orders of magnitude smaller and is sufficient for a portable
    judge/investigation bundle because every included product participates in a
    real SafeSKU candidate relationship.
    """
    asins = _asin_set(candidate_file)
    if not asins:
        raise ValueError("No Amazon parent_asin values found in the linkage candidate artifact.")

    output.parent.mkdir(parents=True, exist_ok=True)
    matched = 0
    scanned = 0
    seen: set[str] = set()

    with source.open("r", encoding="utf-8") as inp, output.open("w", encoding="utf-8", newline="\n") as out:
        for line_number, line in enumerate(inp, start=1):
            scanned = line_number
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {source}:{line_number}: {exc}") from exc
            if not isinstance(obj, dict):
                continue
            asin = str(obj.get("parent_asin") or obj.get("asin") or "").strip().upper()
            if asin in asins and asin not in seen:
                out.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
                seen.add(asin)
                matched += 1

    missing = len(asins - seen)
    print(f"Amazon candidate ASINs: {len(asins):,}")
    print(f"Amazon products scanned: {scanned:,}")
    print(f"Amazon products extracted: {matched:,}")
    print(f"Candidate ASINs missing from normalized catalog: {missing:,}")
    return matched, missing


def _entry(source_type: str, path: Path, member_name: str) -> dict:
    sha, size = sha256_file(path)
    return {
        "source_type": source_type,
        "path": member_name,
        "name": path.name,
        "description": {
            "cpsc": "CPSC historical recall benchmark",
            "saferproducts": "SaferProducts historical consumer-incident benchmark",
            "amazon_products": "Amazon products referenced by SafeSKU linkage candidates",
            "linkage": "SafeSKU Amazon linkage candidate artifact",
        }[source_type],
        "sha256": sha,
        "bytes": size,
    }


def build_bundle(output: Path, product_slice: Path) -> None:
    files = [
        ("cpsc", CPSC, "datasets/cpsc/recalls.jsonl"),
        ("saferproducts", SAFER, "datasets/saferproducts/incidents.jsonl"),
        ("amazon_products", product_slice, "datasets/amazon_products/product_metadata.jsonl"),
        ("linkage", LINKAGE, "datasets/linkage/candidates.jsonl"),
    ]
    for _, path, _ in files:
        if not path.is_file():
            raise SystemExit(f"Required artifact not found: {path}")

    entries = [_entry(source_type, path, member) for source_type, path, member in files]
    manifest = build_manifest(
        entries,
        workspace_name="SafeSKU Judge Investigation Workspace",
        description=(
            "Portable SafeSKU benchmark slice containing official recalls, public safety incidents, "
            "Amazon products referenced by linkage candidates, and the candidate graph. "
            "The full Amazon catalog remains a server-side benchmark artifact rather than a browser upload."
        ),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        for _, path, member in files:
            print(f"Adding: {member} <- {path}")
            zf.write(path, arcname=member)

    print(f"\nCreated: {output}")
    print(f"Bundle ID: {manifest['bundle_id']}")
    print(f"Bundle size: {output.stat().st_size / 1024 / 1024:.1f} MiB")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a portable SafeSKU judge bundle from real benchmark artifacts.")
    parser.add_argument("--source", type=Path, default=AMAZON_PRODUCTS, help="15 GB normalized Amazon product metadata JSONL")
    parser.add_argument("--candidates", type=Path, default=LINKAGE, help="SafeSKU Amazon linkage candidates JSONL")
    parser.add_argument("--slice", type=Path, default=DEFAULT_SLICE, help="Output Amazon product slice JSONL")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output ZIP bundle")
    parser.add_argument("--skip-slice", action="store_true", help="Reuse an existing product slice")
    args = parser.parse_args()

    if not args.skip_slice:
        build_product_slice(args.source, args.candidates, args.slice)
    elif not args.slice.is_file():
        raise SystemExit(f"--skip-slice was used but slice does not exist: {args.slice}")

    build_bundle(args.output, args.slice)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
