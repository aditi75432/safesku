#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.workspace.bundle import build_manifest, sha256_file  # noqa: E402
from app.workspace.schema import detect_source  # noqa: E402

SOURCE_ORDER = ["cpsc", "saferproducts", "amazon_products", "amazon_reviews", "linkage"]
ALIASES = {
    "cpsc": ("cpsc", "recall"),
    "saferproducts": ("saferproducts", "safer", "incident"),
    "amazon_products": ("amazon", "product", "metadata"),
    "amazon_reviews": ("amazon", "review"),
    "linkage": ("linkage", "candidate", "adjudicat"),
}
EXTENSIONS = {".csv", ".json", ".jsonl", ".ndjson", ".gz"}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a SafeSKU Bundle from prepared research artifacts.")
    p.add_argument("--root", type=Path, default=ROOT / "data", help="Directory to scan when --file is not used.")
    p.add_argument("--output", type=Path, default=ROOT / "data" / "bundles" / "safesku-research-bundle.zip")
    p.add_argument("--workspace-name", default="SafeSKU research workspace")
    p.add_argument("--description", default="SafeSKU benchmark artifacts prepared for local investigation.")
    p.add_argument("--file", action="append", nargs=2, metavar=("SOURCE", "PATH"), help="Explicit source and file. Repeat per source.")
    p.add_argument("--dry-run", action="store_true", help="Print the selected files without creating the ZIP.")
    return p


def _headers(path: Path) -> set[str]:
    import csv
    import json as _json
    try:
        with path.open("rb") as raw:
            sample = raw.read(200_000).decode("utf-8-sig", errors="ignore")
    except OSError:
        return set()
    suffixes = {x.lower() for x in path.suffixes}
    try:
        if ".csv" in suffixes:
            first = sample.splitlines()[0] if sample.splitlines() else ""
            return {x.strip() for x in next(csv.reader([first]), [])}
        if suffixes & {".json", ".jsonl", ".ndjson"}:
            line = next((x for x in sample.splitlines() if x.strip()), sample)
            obj = _json.loads(line)
            if isinstance(obj, dict):
                return set(obj.keys())
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                return set(obj[0].keys())
    except Exception:
        return set()
    return set()

def discover(root: Path) -> tuple[list[tuple[str, Path]], dict[str, list[Path]]]:
    grouped: dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        try:
            source = detect_source(_headers(path), path.name)
        except ValueError:
            continue
        grouped.setdefault(source, []).append(path)

    selected: list[tuple[str, Path]] = []
    for source in SOURCE_ORDER:
        rows = sorted(grouped.get(source, []), key=lambda p: (p.stat().st_size, str(p)), reverse=True)
        if len(rows) == 1:
            selected.append((source, rows[0]))
    return selected, grouped


def main() -> int:
    args = parser().parse_args()
    if args.file:
        selected = []
        for source, raw in args.file:
            if source not in SOURCE_ORDER:
                raise SystemExit(f"Unsupported source {source!r}. Use: {', '.join(SOURCE_ORDER)}")
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                raise SystemExit(f"File not found: {path}")
            selected.append((source, path))
    else:
        selected, grouped = discover(args.root.resolve())
        ambiguous = {source: paths for source, paths in grouped.items() if len(paths) > 1}
        if ambiguous:
            print("Several plausible artifacts were found for one or more sources. SafeSKU will not guess.\n")
            for source, paths in ambiguous.items():
                print(f"{source}:")
                for path in sorted(paths):
                    print(f"  {path}")
            raise SystemExit("Use explicit --file SOURCE PATH arguments for ambiguous sources.")

    if not selected:
        raise SystemExit("No bundle candidates were found. Run scripts/inspect_safesku_artifacts.py first.")

    print("SafeSKU Bundle plan")
    print("=" * 72)
    for source, path in selected:
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"{source:16} {size_mb:9.1f} MiB  {path}")
    print()

    if args.dry_run:
        return 0

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    entries = []
    for source, path in selected:
        sha, size = sha256_file(path)
        member_name = f"datasets/{source}/{path.name}"
        entries.append({
            "source_type": source,
            "path": member_name,
            "name": path.name,
            "description": f"{source} artifact",
            "sha256": sha,
            "bytes": size,
        })
    manifest = build_manifest(entries, args.workspace_name, args.description)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        for entry, (_, path) in zip(entries, selected):
            print(f"Adding {entry['source_type']}: {path.name}")
            zf.write(path, arcname=entry["path"])

    print(f"\nCreated: {output}")
    print(f"Bundle ID: {manifest['bundle_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
