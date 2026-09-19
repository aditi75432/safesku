from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterator


JSON_CONTAINER_KEYS = ("data", "results", "items", "recalls", "incidents", "records")


def _open_text(path: Path):
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig")
    return path.open("r", encoding="utf-8-sig")


def iter_records(path: Path) -> Iterator[dict[str, Any]]:
    """Stream flat CSV/JSON/JSONL files without loading the full dataset into memory."""
    suffixes = [s.lower() for s in path.suffixes]
    is_json = ".json" in suffixes
    is_jsonl = ".jsonl" in suffixes or ".ndjson" in suffixes

    if ".csv" in suffixes:
        import csv
        with _open_text(path) as handle:
            yield from csv.DictReader(handle)
        return

    if is_jsonl:
        with _open_text(path) as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value
        return

    if is_json:
        with _open_text(path) as handle:
            value = json.load(handle)
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    yield row
            return
        if isinstance(value, dict):
            for key in JSON_CONTAINER_KEYS:
                nested = value.get(key)
                if isinstance(nested, list):
                    for row in nested:
                        if isinstance(row, dict):
                            yield row
                    return
            yield value
            return

    raise ValueError("SafeSKU currently accepts .csv, .json, .jsonl, .ndjson, and their .gz variants.")
