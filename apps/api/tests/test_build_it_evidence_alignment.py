from __future__ import annotations

from pathlib import Path

from app.investigation.agent import build_safety_case
from app.investigation.store import DataStore
from app.workspace.service import WorkspaceService


def test_workspace_supplied_candidates_are_ranked(tmp_path: Path):
    service = WorkspaceService(tmp_path)
    service.store.save_generated_candidates(
        "22754",
        [
            {
                "parent_asin": "LOW",
                "title": "Unrelated product",
                "exact_upc": 0,
                "shared_token_count": 1,
                "jaccard": 0.05,
                "title_similarity": 0.05,
                "evidence_score": 0.05,
            },
            {
                "parent_asin": "HIGH",
                "title": "Mohnark Lidocaine 4% Topical Anesthetic Cream",
                "exact_upc": 1,
                "shared_token_count": 5,
                "jaccard": 0.6,
                "title_similarity": 0.9,
                "evidence_score": 1.0,
            },
        ],
    )
    service.store.insert_rows(
        "cpsc",
        "CPSC-TEST",
        [
            {
                "recall_number": "22754",
                "source_record_id": "R1",
                "recall_date": "2022-06-30",
                "product_name": "Mohnark Pharmaceuticals Lidocaine 4% Topical Anesthetic Cream",
                "title": "Recall 22754",
                "hazards": [],
                "description": "",
                "url": "",
                "brand": "",
                "model": "",
                "upc": "860002324906",
                "category": "",
            }
        ],
    )
    case = service.case_for_recall("22754")
    assert case is not None
    assert case["amazon_candidates"][0]["parent_asin"] == "HIGH"
    assert case["amazon_candidates"][0]["evidence_score"] == 1.0


def test_build_it_datastore_prefers_active_workspace(tmp_path: Path, monkeypatch):
    service = WorkspaceService(tmp_path)
    monkeypatch.setenv("SAFE_SKU_BUILD_IT", "true")
    monkeypatch.setenv("SAFE_SKU_RUNTIME_DIR", str(tmp_path))

    # This path exists only to make the test independent of bundled demo fixtures.
    service.store.insert_rows(
        "cpsc",
        "CPSC-TEST",
        [
            {
                "recall_number": "55555",
                "source_record_id": "R55555",
                "recall_date": "2023-01-01",
                "product_name": "Workspace Recall",
                "title": "Workspace Recall",
                "hazards": [],
                "description": "",
                "url": "",
                "brand": "",
                "model": "",
                "upc": "",
                "category": "",
            }
        ],
    )

    store = DataStore(tmp_path / "unused.json")
    case = store.find_case("55555")
    assert case is not None
    assert case["recall"]["product_name"] == "Workspace Recall"


def test_historical_timeline_does_not_fake_marketplace_event(tmp_path: Path):
    bundle = {
        "cases": [
            {
                "recall": {
                    "recall_number": "23034",
                    "source_record_id": "R1",
                    "recall_date": "2022-11-03",
                    "product_name": "Demo Steamer",
                    "title": "Demo Steamer recalled",
                    "hazards": [],
                },
                "amazon_candidates": [
                    {"parent_asin": "BTEST", "title": "Demo Steamer", "evidence_score": 0.8, "evidence": ["Title"]}
                ],
                "incidents": [],
            }
        ]
    }
    path = tmp_path / "bundle.json"
    import json

    path.write_text(json.dumps(bundle), encoding="utf-8")
    result = build_safety_case(DataStore(path), "23034", "Investigate recall 23034")
    assert all(event["type"] != "marketplace_identity" for event in result["timeline"])
    assert result["investigation_events"][0]["type"] == "investigation"
