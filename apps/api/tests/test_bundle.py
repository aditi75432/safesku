import io
import json
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app import demo_app
from app.workspace import WorkspaceService
from app.workspace.bundle import build_manifest, sha256_file


def _client(tmp_path: Path):
    demo_app.workspace = WorkspaceService(tmp_path / "runtime")
    return TestClient(demo_app.app)


def _wait_ready(client: TestClient, dataset_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = next(d for d in client.get("/api/workspace/datasets").json()["datasets"] if d["dataset_id"] == dataset_id)
        if row["status"] in {"ready", "failed"}:
            return row
        time.sleep(0.05)
    raise AssertionError("dataset ingestion did not finish")


def _bundle(tmp_path: Path) -> bytes:
    cpsc = tmp_path / "cpsc.json"
    cpsc.write_text(json.dumps([{
        "source_record_id": "cpsc-100",
        "recall_number": "100",
        "recall_date": "2023-06-30",
        "product_name": "Bundle Blender",
        "title": "Bundle Blender recall",
        "hazards": ["Laceration"],
    }]), encoding="utf-8")
    safer = tmp_path / "saferproducts.jsonl"
    safer.write_text(json.dumps({
        "source_record_id": "sp-100",
        "incident_date": "2023-05-01",
        "publication_date": "2023-05-10",
        "product_description": "Bundle Blender",
        "description": "Unsafe blade reported.",
        "cpsc_recall_number": "100",
    }) + "\n", encoding="utf-8")

    entries = []
    for source, path in [("cpsc", cpsc), ("saferproducts", safer)]:
        digest, size = sha256_file(path)
        entries.append({
            "source_type": source,
            "path": f"datasets/{source}/{path.name}",
            "name": path.name,
            "description": f"{source} test artifact",
            "sha256": digest,
            "bytes": size,
        })
    manifest = build_manifest(entries, "Test workspace", "Bundle import test")
    out = tmp_path / "bundle.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for entry, path in zip(entries, [cpsc, safer]):
            zf.write(path, entry["path"])
    return out.read_bytes()


def test_bundle_import_registers_and_ingests(tmp_path):
    client = _client(tmp_path)
    body = client.post(
        "/api/workspace/bundles/import",
        files={"file": ("safesku-test.zip", _bundle(tmp_path), "application/zip")},
    )
    assert body.status_code == 200, body.text
    payload = body.json()["bundle"]
    assert payload["dataset_count"] == 2
    for dataset in payload["datasets"]:
        row = _wait_ready(client, dataset["dataset_id"])
        assert row["status"] == "ready"
        assert row["accepted_count"] == 1
        assert Path(row["file_path"]).exists()

    overview = client.get("/api/workspace/overview").json()
    assert overview["recalls"] == 1
    assert overview["incidents"] == 1
    assert client.get("/api/workspace/bundles").json()["bundles"]


def test_bundle_rejects_checksum_tampering(tmp_path):
    client = _client(tmp_path)
    bundle = bytearray(_bundle(tmp_path))
    # Rebuild a deliberately bad bundle with a valid manifest but modified member content.
    raw = tmp_path / "bad.zip"
    with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = json.loads(zipfile.ZipFile(io.BytesIO(bytes(bundle))).read("manifest.json"))
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("datasets/cpsc/cpsc.json", b"tampered")
        zf.writestr("datasets/saferproducts/saferproducts.jsonl", b"{}\n")
    response = client.post(
        "/api/workspace/bundles/import",
        files={"file": ("bad.zip", raw.read_bytes(), "application/zip")},
    )
    assert response.status_code == 400
    assert "Checksum mismatch" in response.json()["detail"]
