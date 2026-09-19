from __future__ import annotations

import base64
import io
import json
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.local_bundle_upload as module


def _tiny_bundle() -> bytes:
    manifest = {
        "bundle_id": "BND-TEST",
        "format": "safesku-bundle/v1",
        "workspace": {"name": "Test"},
        "datasets": [
            {"id": "D-CPSC", "path": "datasets/cpsc/cpsc.json", "name": "cpsc.json", "source_type": "cpsc", "bytes": 9, "sha256": "ignored"}
        ],
    }
    return_value = b'{}\n'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("datasets/cpsc/cpsc.json", return_value)
    return buf.getvalue()


def test_chunk_upload_reassembles_bytes(tmp_path, monkeypatch):
    app = FastAPI()
    app.include_router(module.router)
    monkeypatch.setattr(module, "UPLOAD_ROOT", tmp_path / "uploads")

    seen = {}

    class FakeWorkspace:
        def import_bundle_stream(self, name, stream):
            seen["name"] = name
            seen["bytes"] = stream.read()
            return {"bundle_id": "BND-X", "bundle_file": name, "workspace": {}, "datasets": []}

        class FakeStore:
            def add_bundle(self, *args): pass
            def add_bundle_dataset(self, *args): pass

        store = FakeStore()

    monkeypatch.setattr(module, "_workspace", lambda: FakeWorkspace())
    client = TestClient(app)
    payload = _tiny_bundle()

    start = client.post("/api/workspace/bundles/upload/start", json={"filename": "demo.zip", "size_bytes": len(payload)})
    assert start.status_code == 200
    data = start.json()

    chunk_size = data["chunk_size"]
    total = data["total_chunks"]
    for index in range(total):
        chunk = payload[index * chunk_size:(index + 1) * chunk_size]
        body = {
            "upload_id": data["upload_id"],
            "chunk_index": index,
            "total_chunks": total,
            "data": base64.b64encode(chunk).decode("ascii"),
        }
        assert client.post("/api/workspace/bundles/upload/chunk", json=body).status_code == 200

    complete = client.post(
        "/api/workspace/bundles/upload/complete",
        json={"upload_id": data["upload_id"], "total_chunks": total},
    )
    assert complete.status_code == 200
    assert seen["name"] == "demo.zip"
    assert seen["bytes"] == payload
