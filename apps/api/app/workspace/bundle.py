from __future__ import annotations

import hashlib
import json
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterable

from .schema import SOURCE_TYPES

BUNDLE_FORMAT = "safesku.bundle.v1"
MAX_MANIFEST_BYTES = 1_000_000


def _safe_member_name(name: str) -> str:
    """Reject archive paths that could escape the extraction directory."""
    normalized = name.replace("\\", "/").strip("/")
    if not normalized or normalized.startswith("../") or "/../" in normalized or normalized == "..":
        raise ValueError(f"Unsafe bundle member path: {name!r}")
    if re.match(r"^[A-Za-z]:/", normalized):
        raise ValueError(f"Absolute Windows path is not allowed: {name!r}")
    return normalized


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("format") != BUNDLE_FORMAT:
        raise ValueError(f"Unsupported bundle format: {manifest.get('format')!r}")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("Bundle manifest must contain at least one dataset.")
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in datasets:
        if not isinstance(item, dict):
            raise ValueError("Each manifest dataset must be an object.")
        source_type = str(item.get("source_type") or "").strip()
        path = _safe_member_name(str(item.get("path") or ""))
        if source_type not in SOURCE_TYPES:
            raise ValueError(f"Unsupported source_type in bundle: {source_type!r}")
        if path in seen:
            raise ValueError(f"Duplicate bundle dataset path: {path}")
        seen.add(path)
        sha256 = str(item.get("sha256") or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError(f"Invalid SHA-256 for {path}.")
        validated.append({
            "source_type": source_type,
            "path": path,
            "name": str(item.get("name") or Path(path).name),
            "description": str(item.get("description") or ""),
            "sha256": sha256,
            "bytes": int(item.get("bytes") or 0),
        })
    return validated


def read_manifest(zf: zipfile.ZipFile) -> dict[str, Any]:
    try:
        info = zf.getinfo("manifest.json")
    except KeyError as exc:
        raise ValueError("SafeSKU bundle is missing manifest.json.") from exc
    if info.file_size > MAX_MANIFEST_BYTES:
        raise ValueError("Bundle manifest is unexpectedly large.")
    try:
        manifest = json.loads(zf.read(info).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Bundle manifest.json is not valid UTF-8 JSON.") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Bundle manifest must be a JSON object.")
    _validate_manifest(manifest)
    return manifest


def build_manifest(entries: Iterable[dict[str, Any]], workspace_name: str = "SafeSKU workspace", description: str = "") -> dict[str, Any]:
    datasets = []
    for item in entries:
        datasets.append(dict(item))
    return {
        "format": BUNDLE_FORMAT,
        "bundle_id": f"BND-{uuid.uuid4().hex[:12].upper()}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workspace": {"name": workspace_name, "description": description},
        "datasets": datasets,
    }
