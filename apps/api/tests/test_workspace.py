from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from app import demo_app
from app.workspace import WorkspaceService


def _client(tmp_path):
    demo_app.workspace = WorkspaceService(tmp_path / "runtime")
    return TestClient(demo_app.app)


def _wait_ready(client: TestClient, dataset_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get("/api/workspace/datasets").json()["datasets"]
        row = next(d for d in body if d["dataset_id"] == dataset_id)
        if row["status"] in {"ready", "failed"}:
            return row
        time.sleep(0.05)
    raise AssertionError("dataset ingestion did not finish")


def test_upload_ingest_search_and_investigate(tmp_path):
    client = _client(tmp_path)

    cpsc = [
        {
            "source_record_id": "cpsc-12345",
            "recall_number": "12345",
            "recall_date": "2023-06-30",
            "product_name": "Demo Blender",
            "title": "Demo Blender recalled",
            "hazards": ["Laceration"],
        }
    ]
    safer = [
        {
            "source_record_id": "sp-1",
            "incident_date": "2023-05-01",
            "publication_date": "2023-05-10",
            "product_description": "Demo Blender",
            "description": "Unsafe blade reported on Amazon.",
            "cpsc_recall_number": "12345",
        }
    ]
    products = [
        {"parent_asin": "B123456789", "title": "Demo Blender", "brand": "Demo", "category": "Kitchen"},
        {"parent_asin": "B987654321", "title": "Unrelated Lamp", "brand": "Other", "category": "Home"},
    ]

    ids = []
    for name, rows, source in [("cpsc.json", cpsc, "cpsc"), ("saferproducts.jsonl", safer, "saferproducts"), ("amazon.jsonl", products, "amazon_products")]:
        if name.endswith(".jsonl"):
            body = "".join(json.dumps(row) + "\n" for row in rows).encode()
        else:
            body = json.dumps(rows).encode()
        response = client.post(
            "/api/workspace/datasets/upload",
            params={"source_type": source},
            files={"file": (name, body, "application/octet-stream")},
        )
        assert response.status_code == 200, response.text
        ids.append(response.json()["dataset"]["dataset_id"])

    for dataset_id in ids:
        row = _wait_ready(client, dataset_id)
        assert row["status"] == "ready"
        expected = 2 if dataset_id == ids[2] else 1
        assert row["accepted_count"] == expected

    search = client.get("/api/search?q=Demo%20Blender").json()
    assert any(r.get("recall_number") == "12345" for r in search["results"])

    investigation = client.post("/api/investigations", json={"query": "Investigate recall 12345"})
    assert investigation.status_code == 200, investigation.text
    body = investigation.json()
    assert body["recall"]["recall_number"] == "12345"
    assert body["amazon_candidates"]
    assert body["derived_signals"]["pre_recall_public_incident_count"] == 1

    queue = client.get("/api/workspace/review-queue").json()
    assert queue["items"]

    asin = body["amazon_candidates"][0]["parent_asin"]
    review = client.post(
        "/api/reviews",
        json={"recall_number": "12345", "parent_asin": asin, "decision": "MATCH", "note": "Reviewed in workspace"},
    )
    assert review.status_code == 200

    rerun = client.post("/api/investigations", json={"query": "Investigate recall 12345"}).json()
    assert rerun["amazon_candidates"][0]["review_label"] == "MATCH"


def test_source_detection_rejects_unknown_file(tmp_path):
    client = _client(tmp_path)
    response = client.post(
        "/api/workspace/datasets/upload",
        files={"file": ("mystery.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
