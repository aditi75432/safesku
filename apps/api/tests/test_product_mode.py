from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import demo_app
from app.investigation.store import DataStore


def _seed(tmp_path):
    bundle = {
        "cases": [
            {
                "recall": {
                    "recall_number": "99999",
                    "source_record_id": "cpsc-99999",
                    "recall_date": "2023-06-30",
                    "product_name": "Demo Blender",
                    "title": "Demo Blender Recalled",
                    "hazards": ["Laceration"],
                },
                "incidents": [
                    {
                        "source_record_id": "sp-1",
                        "incident_date": "2023-05-01",
                        "publication_date": "2023-05-10",
                        "product_description": "Demo Blender",
                        "description": "Reported unsafe blade.",
                    }
                ],
                "amazon_candidates": [
                    {"parent_asin": "B000000001", "title": "Demo Blender", "evidence_score": 0.91, "review_label": "UNCERTAIN"}
                ],
            }
        ]
    }
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    demo_app.store = DataStore(path)
    demo_app._history.clear()
    demo_app._review_decisions.clear()
    return TestClient(demo_app.app)


def test_search_review_and_export(tmp_path, monkeypatch):
    client = _seed(tmp_path)
    r = client.get("/api/search?q=blender")
    assert r.status_code == 200
    assert r.json()["results"][0]["recall_number"] == "99999"

    r = client.post(
        "/api/reviews",
        json={"recall_number": "99999", "parent_asin": "B000000001", "decision": "MATCH", "note": "UPC/title review"},
    )
    assert r.status_code == 200

    r = client.post("/api/investigations", json={"query": "Investigate recall 99999"})
    assert r.status_code == 200
    body = r.json()
    assert body["amazon_candidates"][0]["review_label"] == "MATCH"
    assert body["derived_signals"]["identity_status"] == "working_match"

    r = client.get("/api/investigations/99999/export?format=csv")
    assert r.status_code == 200
    assert "B000000001" in r.text
