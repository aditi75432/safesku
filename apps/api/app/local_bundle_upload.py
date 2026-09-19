"""SAM Local-safe bundle upload using JSON/base64 chunks.

SAM Local can fail while proxying raw multipart/binary request bodies. This
router keeps bundle bytes out of the HTTP binary path by sending small ASCII
base64 chunks as JSON. The browser still presents this as one file upload.

Bundle ingestion is submitted to a local worker thread after registration so the
Lambda invocation can return before SQLite ingestion of the Amazon slice runs.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .local_ingestion import submit_ingestion

router = APIRouter(prefix="/api/workspace/bundles/upload", tags=["workspace-upload"])

UPLOAD_ROOT = Path("data/runtime/sam_bundle_uploads")
MAX_BYTES = 500 * 1024 * 1024
CHUNK_SIZE = 1 * 1024 * 1024
_UPLOAD_ID_RE = re.compile(r"^UPL-[A-F0-9]{24}$")


class UploadStartRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0, le=MAX_BYTES)


class UploadChunkRequest(BaseModel):
    upload_id: str = Field(min_length=28, max_length=28)
    chunk_index: int = Field(ge=0)
    total_chunks: int = Field(gt=0)
    data: str = Field(min_length=1)


class UploadCompleteRequest(BaseModel):
    upload_id: str = Field(min_length=28, max_length=28)
    total_chunks: int = Field(gt=0)


def _session(upload_id: str) -> Path:
    if not _UPLOAD_ID_RE.fullmatch(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload session.")
    path = UPLOAD_ROOT / upload_id
    if not path.exists():
        raise HTTPException(status_code=404, detail="Upload session was not found.")
    return path


def _part_path(session: Path, index: int) -> Path:
    return session / f"chunk-{index:06d}.part"


def _workspace() -> Any:
    # Lazy import avoids a module cycle because demo_app includes this router.
    from .demo_app import workspace
    return workspace


@router.post("/start")
def start_upload(request: UploadStartRequest) -> dict[str, Any]:
    if not request.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="SafeSKU Bundle must be a .zip file.")

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    upload_id = f"UPL-{uuid.uuid4().hex[:24].upper()}"
    session = UPLOAD_ROOT / upload_id
    session.mkdir(parents=True, exist_ok=False)
    metadata = {
        "filename": Path(request.filename).name,
        "size_bytes": request.size_bytes,
        "chunk_size": CHUNK_SIZE,
        "total_chunks": (request.size_bytes + CHUNK_SIZE - 1) // CHUNK_SIZE,
    }
    (session / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return {
        "ok": True,
        "upload_id": upload_id,
        "chunk_size": CHUNK_SIZE,
        "total_chunks": metadata["total_chunks"],
    }


@router.post("/chunk")
def upload_chunk(request: UploadChunkRequest) -> dict[str, Any]:
    session = _session(request.upload_id)
    metadata_path = session / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    total_chunks = int(metadata["total_chunks"])
    if request.total_chunks != total_chunks:
        raise HTTPException(status_code=400, detail="Chunk count does not match upload session.")
    if request.chunk_index >= total_chunks:
        raise HTTPException(status_code=400, detail="Chunk index is out of range.")

    try:
        raw = base64.b64decode(request.data.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail="Chunk is not valid base64 data.") from exc

    expected = CHUNK_SIZE if request.chunk_index < total_chunks - 1 else int(metadata["size_bytes"]) - CHUNK_SIZE * (total_chunks - 1)
    if len(raw) != expected:
        raise HTTPException(status_code=400, detail=f"Chunk {request.chunk_index} has {len(raw)} bytes; expected {expected}.")

    _part_path(session, request.chunk_index).write_bytes(raw)
    return {"ok": True, "upload_id": request.upload_id, "chunk_index": request.chunk_index}


@router.post("/complete")
def complete_upload(request: UploadCompleteRequest) -> dict[str, Any]:
    session = _session(request.upload_id)
    metadata = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
    total_chunks = int(metadata["total_chunks"])
    if request.total_chunks != total_chunks:
        raise HTTPException(status_code=400, detail="Chunk count does not match upload session.")

    parts = [_part_path(session, i) for i in range(total_chunks)]
    missing = [str(i) for i, path in enumerate(parts) if not path.exists()]
    if missing:
        raise HTTPException(status_code=409, detail=f"Upload is incomplete. Missing chunks: {', '.join(missing[:10])}.")

    assembled = session / metadata["filename"]
    try:
        with assembled.open("wb") as output:
            for part in parts:
                with part.open("rb") as source:
                    shutil.copyfileobj(source, output, length=CHUNK_SIZE)

        if assembled.stat().st_size != int(metadata["size_bytes"]):
            raise HTTPException(status_code=400, detail="Uploaded bundle size does not match the declared size.")

        workspace = _workspace()
        # Bundle validation, extraction, and dataset registration are synchronous;
        # this gives the client a reliable success response before long ingestion.
        with assembled.open("rb") as stream:
            result = workspace.import_bundle_stream(metadata["filename"], stream)

        workspace.store.add_bundle(
            result["bundle_id"],
            result["bundle_file"],
            str((result.get("workspace") or {}).get("name") or "SafeSKU workspace"),
            str((result.get("workspace") or {}).get("description") or ""),
        )
        dataset_ids: list[str] = []
        for dataset in result["datasets"]:
            workspace.store.add_bundle_dataset(
                result["bundle_id"],
                dataset["dataset_id"],
                dataset.get("bundle_member_path", dataset["file_name"]),
                dataset["source_type"],
            )
            if dataset.get("status") == "queued":
                dataset_ids.append(dataset["dataset_id"])

        ingestion_started = submit_ingestion(workspace, dataset_ids)
        return {
            "ok": True,
            "bundle": result,
            "ingestion": {
                "status": "started" if ingestion_started else "not_required",
                "dataset_ids": dataset_ids,
            },
        }
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        # Extracted dataset files have already been copied/moved into the durable
        # workspace before the upload session is removed.
        shutil.rmtree(session, ignore_errors=True)
