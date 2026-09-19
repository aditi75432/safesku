#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.workspace.schema import detect_source

VALID_SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson", ".gz"}
KEYWORDS = {
    "cpsc": ("cpsc", "recall"),
    "saferproducts": ("safer", "incident"),
    "amazon_products": ("amazon", "metadata", "product"),
    "amazon_reviews": ("amazon", "review"),
    "linkage": ("linkage", "candidate", "adjudicat"),
}


def preview_headers(path: Path) -> set[str]:
    try:
        with path.open("rb") as raw:
            sample = raw.read(200_000).decode("utf-8-sig", errors="ignore")
    except OSError:
        return set()
    lower = {s.lower() for s in path.suffixes}
    try:
        if ".csv" in lower:
            first = sample.splitlines()[0] if sample.splitlines() else ""
            return {x.strip() for x in next(csv.reader([first]), [])}
        line = next((x for x in sample.splitlines() if x.strip()), sample)
        obj = json.loads(line)
        if isinstance(obj, dict):
            return set(obj.keys())
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return set(obj[0].keys())
    except Exception:
        return set()
    return set()


def likely_source(path: Path, headers: set[str]) -> str:
    try:
        return detect_source(headers, path.name)
    except ValueError:
        return "unknown"


def main() -> int:
    p = argparse.ArgumentParser(description="Inspect SafeSKU research artifacts before building a bundle.")
    p.add_argument("root", type=Path, nargs="?", default=Path("data"))
    args = p.parse_args()
    root = args.root.resolve()
    if not root.exists():
        raise SystemExit(f"Directory not found: {root}")
    rows = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in VALID_SUFFIXES:
            continue
        headers = preview_headers(path)
        rows.append((likely_source(path, headers), path, path.stat().st_size, ", ".join(sorted(headers))[:160]))
    rows.sort(key=lambda x: (x[0], str(x[1])))
    print(f"SafeSKU artifact candidates under {root}")
    print("-" * 110)
    print(f"{'SOURCE':16} {'MiB':>10}  {'PATH':60}  HEADERS")
    print("-" * 110)
    for source, path, size, headers in rows:
        short = str(path)
        if len(short) > 60:
            short = "..." + short[-57:]
        print(f"{source:16} {size/1024/1024:10.1f}  {short:60}  {headers}")
    print("-" * 110)
    print(f"Found {len(rows)} candidate files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
