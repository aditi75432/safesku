"""Small read-only investigation tools exposed to the agent layer.

The functions are intentionally deterministic and evidence-returning. They make it
possible to keep the LLM outside the source-of-truth path.
"""
from __future__ import annotations

from .store import DataStore, is_pre_recall_public


store = DataStore()


def search_cpsc_recall(recall_number: str) -> dict:
    case = store.find_case(recall_number)
    return {"recall": case["recall"]} if case else {"error": "recall_not_found"}


def find_amazon_candidates(recall_number: str) -> dict:
    case = store.find_case(recall_number)
    return {"candidates": case.get("amazon_candidates", [])[:10]} if case else {"error": "recall_not_found"}


def get_saferproducts_incidents(recall_number: str) -> dict:
    case = store.find_case(recall_number)
    return {"incidents": case.get("incidents", [])} if case else {"error": "recall_not_found"}


def build_safety_timeline(recall_number: str) -> dict:
    case = store.find_case(recall_number)
    if not case:
        return {"error": "recall_not_found"}
    recall = case["recall"]
    events = []
    for incident in case.get("incidents", []):
        events.append({
            "date": incident.get("publication_date") or incident.get("incident_date"),
            "source": "SaferProducts.gov",
            "pre_recall_public": is_pre_recall_public(incident, recall.get("recall_date", "")),
        })
    events.append({"date": recall.get("recall_date"), "source": "CPSC", "pre_recall_public": False})
    return {"events": sorted(events, key=lambda x: x.get("date") or "9999-99-99")}
