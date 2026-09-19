from __future__ import annotations

from pathlib import Path

from app.investigation.agent import _extract_recall_number, build_safety_case
from app.investigation.store import DataStore


def fixture_store(tmp_path: Path) -> DataStore:
    bundle = {
        "cases": [{
            "recall": {
                "recall_number": "23034",
                "source_record_id": "R1",
                "recall_date": "2022-11-03",
                "product_name": "BLACK+DECKER Model HGS011 Easy Garment Steamers",
                "title": "Garment Steamers recalled due to burn hazard",
                "description": "test",
                "hazards": [{"name": "burn hazard"}],
                "url": "https://example.test/cpsc/23034",
            },
            "amazon_candidates": [{
                "parent_asin": "BTEST",
                "title": "BLACK+DECKER HGS011F Easy Garment Steamer",
                "brand": "BLACK+DECKER",
                "model": "HGS011F",
                "exact_upc": 1,
                "evidence_score": 1.0,
                "evidence": ["Exact UPC agreement"],
            }],
            "incidents": [{
                "source_record_id": "S1",
                "incident_date": "2022-05-22",
                "publication_date": "2022-06-08",
                "brand": "Black & Decker",
                "model": "HGS011F",
                "product_description": "Black and Decker HGS011F Easy Garment Steamer",
                "description": "Boiling water came out of the steamer.",
                "manufacturer": "Spectrum Brands, Inc.",
                "retailer": "WAL-MART",
            }],
        }]
    }
    path = tmp_path / "bundle.json"
    import json
    path.write_text(json.dumps(bundle), encoding="utf-8")
    return DataStore(path)


def test_recall_number_extraction():
    assert _extract_recall_number("Investigate CPSC recall 23034") == "23034"
    assert _extract_recall_number("show 12") is None


def test_build_safety_case_is_evidence_grounded(tmp_path: Path):
    store = fixture_store(tmp_path)
    result = build_safety_case(store, "23034", "Investigate CPSC recall 23034")
    assert result["status"] == "completed"
    assert result["amazon_candidates"][0]["parent_asin"] == "BTEST"
    assert any(f["type"] == "temporal_signal" for f in result["findings"])
    temporal = [f for f in result["findings"] if f["type"] == "temporal_signal"][0]
    assert any(e.startswith("E-SP-23034") for e in temporal["evidence_ids"])
