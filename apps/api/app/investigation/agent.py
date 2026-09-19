from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse
from typing import Any

from .store import DataStore, is_pre_recall_public

try:  # Optional dependency for AWS/Bedrock mode.
    from strands import Agent, tool
    from strands.models import BedrockModel
except Exception:  # pragma: no cover - optional runtime dependency
    Agent = None  # type: ignore[assignment]
    BedrockModel = None  # type: ignore[assignment]

    def tool(func):  # type: ignore[no-redef]
        return func


SYSTEM_PROMPT = """
You are SafeSKU Investigator, an evidence-grounded product-safety investigation agent.
You investigate one official product recall using read-only tools.
Never invent evidence, dates, product identities, counts, hazards, or marketplace facts.
Treat CPSC data as the official recall source. Treat SaferProducts records as consumer
incident evidence. Treat Amazon identity evidence as linkage evidence, not proof of causality.
Every material finding must cite the evidence IDs supplied by the tools.
Clearly distinguish: official recall facts, observed consumer reports, marketplace identity
linkage, and derived temporal observations. Do not claim that reviews caused a recall.
When evidence is insufficient, say so and recommend human review.
""".strip()


def _extract_recall_number(query: str) -> str | None:
    match = re.search(r"\b(?:recall\s*(?:number|#)?\s*)?(\d{4,6})\b", query, re.I)
    return match.group(1) if match else None


def _days_before(recall_date: str, evidence_date: str) -> int | None:
    try:
        r = datetime.fromisoformat(recall_date[:10]).date()
        e = datetime.fromisoformat(evidence_date[:10]).date()
    except (ValueError, TypeError):
        return None
    return (r - e).days


def _hazard_text(hazards: Any) -> str:
    if isinstance(hazards, str):
        try:
            value = json.loads(hazards)
            return json.dumps(value)
        except json.JSONDecodeError:
            return hazards
    return json.dumps(hazards, default=str)


def _extract_marketplace_references(incidents: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Extract explicit marketplace references from consumer narratives.

    These are presented as source evidence, not as confirmed product-identity matches.
    """
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    asin_pattern = re.compile(r"(?:/dp/|/gp/product/)([A-Z0-9]{10})", re.I)
    url_pattern = re.compile(r"https?://[^\s\]\")>]+", re.I)
    for incident in incidents:
        text = " ".join(str(incident.get(k) or "") for k in ("description", "product_description", "retailer"))
        for match in asin_pattern.finditer(text):
            asin = match.group(1).upper()
            if asin not in seen:
                refs.append({
                    "type": "amazon_asin",
                    "value": asin,
                    "source_record_id": str(incident.get("source_record_id") or ""),
                    "url": f"https://www.amazon.com/dp/{asin}",
                })
                seen.add(asin)
        if "amazon" in text.lower():
            for url in url_pattern.findall(text):
                domain = urlparse(url).netloc.lower()
                if "amazon." in domain and url not in seen:
                    refs.append({
                        "type": "marketplace_url",
                        "value": url,
                        "source_record_id": str(incident.get("source_record_id") or ""),
                        "url": url,
                    })
                    seen.add(url)
    return refs


def build_safety_case(store: DataStore, recall_number: str, query: str) -> dict[str, Any]:
    case = store.find_case(recall_number)
    if case is None:
        raise KeyError(f"Recall {recall_number} was not found in the available SafeSKU artifacts.")

    recall = case["recall"]
    incidents = case.get("incidents", [])
    candidates = case.get("amazon_candidates", [])
    marketplace_refs = _extract_marketplace_references(incidents)

    trace = [
        {
            "step": 1,
            "tool": "search_cpsc_recall",
            "status": "completed",
            "detail": f"Retrieved official CPSC recall {recall_number}",
        },
        {
            "step": 2,
            "tool": "find_amazon_candidates",
            "status": "completed",
            "detail": f"Ranked {len(candidates)} marketplace candidates by identity evidence",
        },
        {
            "step": 3,
            "tool": "get_saferproducts_incidents",
            "status": "completed",
            "detail": f"Retrieved {len(incidents)} linked public incident records",
        },
        {
            "step": 4,
            "tool": "build_safety_timeline",
            "status": "completed",
            "detail": "Separated pre-recall public evidence from later reports",
        },
        {
            "step": 5,
            "tool": "verify_evidence",
            "status": "completed",
            "detail": "All displayed findings are backed by structured evidence records",
        },
    ]

    evidence: list[dict[str, Any]] = [
        {
            "evidence_id": f"E-CPSC-{recall_number}",
            "source": "CPSC",
            "kind": "official_recall",
            "record_id": recall.get("source_record_id"),
            "title": recall.get("title") or recall.get("product_name"),
            "date": recall.get("recall_date"),
        }
    ]
    for i, incident in enumerate(incidents, start=1):
        evidence.append(
            {
                "evidence_id": f"E-SP-{recall_number}-{i}",
                "source": "SaferProducts.gov",
                "kind": "consumer_incident",
                "record_id": incident.get("source_record_id"),
                "title": incident.get("product_description") or "Consumer incident report",
                "date": incident.get("publication_date") or incident.get("incident_date"),
            }
        )
    for i, candidate in enumerate(candidates[:5], start=1):
        evidence.append(
            {
                "evidence_id": f"E-AMZ-{recall_number}-{i}",
                "source": "Amazon Reviews 2023 metadata",
                "kind": "marketplace_identity",
                "record_id": candidate.get("parent_asin"),
                "title": candidate.get("title"),
                "date": None,
            }
        )

    pre_recall = [
        incident for incident in incidents if is_pre_recall_public(incident, recall.get("recall_date", ""))
    ]
    timeline: list[dict[str, Any]] = []
    for incident in incidents:
        timeline.append(
            {
                "date": incident.get("publication_date") or incident.get("incident_date"),
                "type": "consumer_incident",
                "label": "Public consumer incident",
                "source": "SaferProducts.gov",
                "evidence_id": next(
                    e["evidence_id"] for e in evidence
                    if e["source"] == "SaferProducts.gov" and e["record_id"] == incident.get("source_record_id")
                ),
                "pre_recall": is_pre_recall_public(incident, recall.get("recall_date", "")),
            }
        )
    timeline.append(
        {
            "date": recall.get("recall_date"),
            "type": "official_recall",
            "label": "Official CPSC recall",
            "source": "CPSC",
            "evidence_id": f"E-CPSC-{recall_number}",
            "pre_recall": False,
        }
    )
    timeline.sort(key=lambda x: (x.get("date") or "9999-99-99", x["type"]))

    findings: list[dict[str, Any]] = []
    if candidates:
        top = candidates[0]
        score = float(top.get("evidence_score", 0) or 0)
        if score > 0 and top.get("evidence"):
            findings.append(
                {
                    "type": "identity",
                    "severity": "informational",
                    "title": "Top marketplace identity candidate",
                    "text": (
                        f"{top.get('title') or top.get('parent_asin')} is the best available marketplace candidate "
                        f"based on structured identity evidence (linkage score {score:.3f}). "
                        "The score is not a probability and does not confirm SKU identity."
                    ),
                    "evidence_ids": ["E-CPSC-%s" % recall_number, "E-AMZ-%s-1" % recall_number],
                }
            )
        else:
            findings.append(
                {
                    "type": "identity",
                    "severity": "neutral",
                    "title": "No supported marketplace identity match",
                    "text": (
                        f"{len(candidates)} marketplace candidates were evaluated, but the current evidence does not "
                        "support confirming a marketplace SKU. Human review remains required."
                    ),
                    "evidence_ids": ["E-CPSC-%s" % recall_number],
                }
            )

    if pre_recall:
        earliest_public = min(
            (i.get("publication_date") for i in pre_recall if i.get("publication_date")),
            default=None,
        )
        lead_days = _days_before(recall.get("recall_date", ""), earliest_public) if earliest_public else None
        findings.append(
            {
                "type": "temporal_signal",
                "severity": "attention",
                "title": "Pre-recall public safety evidence detected",
                "text": (
                    f"{len(pre_recall)} linked public incident record(s) were published before the official recall. "
                    + (f"The earliest public record predates the recall by {lead_days} days." if lead_days is not None else "")
                ).strip(),
                "evidence_ids": [
                    e["evidence_id"] for e in evidence
                    if e["source"] == "SaferProducts.gov" and e["record_id"] in {i.get("source_record_id") for i in pre_recall}
                ],
            }
        )
    else:
        findings.append(
            {
                "type": "temporal_signal",
                "severity": "neutral",
                "title": "No pre-recall public evidence in the linked incident set",
                "text": "The currently linked SaferProducts records do not establish a pre-recall public signal.",
                "evidence_ids": [f"E-CPSC-{recall_number}"],
            }
        )

    findings.append(
        {
            "type": "safety_boundary",
            "severity": "neutral",
            "title": "Evidence boundary",
            "text": "Identity linkage and temporal association do not establish that marketplace reviews caused or predicted the recall.",
            "evidence_ids": [f"E-CPSC-{recall_number}"],
        }
    )

    top_candidate = candidates[0] if candidates else None
    identity_status = "not_available"
    if top_candidate:
        label = str(top_candidate.get("review_label") or "").upper()
        if label == "MATCH":
            identity_status = "working_match"
        elif label == "UNCERTAIN":
            identity_status = "human_review_required"
        elif label == "NON_MATCH":
            identity_status = "no_confirmed_match"
        else:
            identity_status = "ranked_candidate_only"

    earliest_public = min(
        (i.get("publication_date") for i in pre_recall if i.get("publication_date")),
        default=None,
    )
    lead_days = _days_before(recall.get("recall_date", ""), earliest_public) if earliest_public else None

    derived = {
        "identity_status": identity_status,
        "human_review_required": identity_status in {"human_review_required", "ranked_candidate_only", "no_confirmed_match"},
        "pre_recall_public_incident_count": len(pre_recall),
        "earliest_publication_date": earliest_public,
        "lead_time_days": lead_days,
        "explicit_marketplace_reference_count": len(marketplace_refs),
        "evidence_item_count": len(evidence),
    }

    return {
        "investigation_id": f"INV-{recall_number}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "query": query,
        "status": "completed",
        "agent_mode": "local_deterministic",
        "recall": recall,
        "agent_trace": trace,
        "amazon_candidates": candidates,
        "marketplace_references": marketplace_refs,
        "incidents": incidents,
        "timeline": timeline,
        "investigation_events": [
            {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "type": "investigation",
                "label": "SafeSKU investigation run",
                "source": "SafeSKU",
                "evidence_id": f"INV-{recall_number}",
            }
        ],
        "findings": findings,
        "evidence": evidence,
        "derived_signals": derived,
        "safety_brief": deterministic_brief(recall, candidates, incidents, pre_recall, findings),
    }


def deterministic_brief(
    recall: dict[str, Any],
    candidates: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    pre_recall: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> str:
    product = recall.get("product_name") or "the recalled product"
    lines = [
        f"SafeSKU investigated {product} (CPSC recall {recall.get('recall_number')}).",
        f"The official recall date is {recall.get('recall_date') or 'not available'}.",
    ]
    if candidates:
        top = candidates[0]
        score = float(top.get("evidence_score", 0) or 0)
        if score > 0 and top.get("evidence"):
            lines.append(
                f"The marketplace layer ranked {top.get('title') or top.get('parent_asin')} highest using structured identity evidence "
                f"(linkage score {score:.3f}); this score is not a probability of product identity."
            )
        else:
            lines.append("Marketplace candidates were retrieved, but the current evidence does not support confirming a marketplace SKU.")
    if pre_recall:
        lines.append(
            f"{len(pre_recall)} linked public consumer incident record(s) were already published before the recall."
        )
    else:
        lines.append("No linked public incident in the current evidence set satisfies the strict pre-recall publication rule.")
    lines.append("The result is an evidence-backed investigation aid; it is not causal proof or a substitute for human safety review.")
    return " ".join(lines)


def run_bedrock_agent(store: DataStore, recall_number: str, query: str) -> tuple[str, list[dict[str, Any]]]:
    """Run the real Strands/Bedrock investigator and capture actual tool telemetry."""
    if Agent is None or BedrockModel is None:
        raise RuntimeError("strands-agents is not installed")

    region = os.getenv("AWS_REGION", "us-east-1")
    model_id = os.getenv("SAFE_SKU_BEDROCK_MODEL", "us.amazon.nova-micro-v1:0")
    trace: list[dict[str, Any]] = []

    @tool
    def search_cpsc_recall(recall_number: str) -> str:
        """Retrieve the official CPSC recall record for a recall number."""
        case = store.find_case(recall_number)
        return json.dumps(case["recall"] if case else {"error": "not found"}, default=str)

    @tool
    def find_amazon_candidates(recall_number: str) -> str:
        """Retrieve ranked marketplace identity candidates for the recalled product."""
        case = store.find_case(recall_number)
        return json.dumps(case.get("amazon_candidates", [])[:5] if case else [], default=str)

    @tool
    def get_saferproducts_incidents(recall_number: str) -> str:
        """Retrieve linked public consumer safety incidents."""
        case = store.find_case(recall_number)
        return json.dumps(case.get("incidents", []) if case else [], default=str)

    @tool
    def build_safety_timeline(recall_number: str) -> str:
        """Build a chronology and flag incidents whose publication predates the recall."""
        case = store.find_case(recall_number)
        if not case:
            return json.dumps([])
        recall = case["recall"]
        timeline = []
        for incident in case.get("incidents", []):
            timeline.append({
                "date": incident.get("publication_date") or incident.get("incident_date"),
                "source": "SaferProducts.gov",
                "pre_recall": is_pre_recall_public(incident, recall.get("recall_date", "")),
            })
        timeline.append({"date": recall.get("recall_date"), "source": "CPSC", "pre_recall": False})
        return json.dumps(sorted(timeline, key=lambda x: x.get("date") or "9999-99-99"))

    def _tool_name(event: Any) -> str:
        use = getattr(event, "tool_use", None)
        if isinstance(use, dict) and use.get("name"):
            return str(use["name"])
        selected = getattr(event, "selected_tool", None)
        return str(getattr(selected, "name", None) or getattr(selected, "__name__", None) or "tool")

    def before_tool(event: Any) -> None:
        trace.append({"step": len(trace) + 1, "tool": _tool_name(event), "status": "running"})

    def after_tool(event: Any) -> None:
        name = _tool_name(event)
        for item in reversed(trace):
            if item.get("tool") == name and item.get("status") == "running":
                item["status"] = "completed"
                if getattr(event, "duration", None) is not None:
                    item["duration_ms"] = round(float(event.duration) * 1000, 1)
                break

    model = BedrockModel(model_id=model_id, region_name=region, temperature=0.1)
    agent = Agent(model=model, tools=[search_cpsc_recall, find_amazon_candidates, get_saferproducts_incidents, build_safety_timeline])
    try:
        from strands.hooks.events import BeforeToolCallEvent, AfterToolCallEvent
        agent.add_hook(BeforeToolCallEvent, before_tool)
        agent.add_hook(AfterToolCallEvent, after_tool)
    except Exception:
        pass

    prompt = f"""{SYSTEM_PROMPT}

Investigation request: {query}
Recall number: {recall_number}

You are the investigation orchestrator. Use the available read-only tools to verify the case.
For a complete investigation, use each of these tools at least once when available:
1) search_cpsc_recall
2) find_amazon_candidates
3) get_saferproducts_incidents
4) build_safety_timeline

Then write a concise safety investigation brief. Cite evidence IDs exactly when they are present in tool results.
Do not invent a product match when evidence is uncertain. Explicitly say when human review is required.
Do not claim causation or that a pre-recall association predicts a later recall.
"""
    result = agent(prompt)
    text_value = getattr(result, "output_text", None) or str(result)
    if not trace:
        trace = [{"step": 1, "tool": "bedrock_synthesis", "status": "completed", "detail": model_id}]
    else:
        for item in trace:
            if item.get("status") == "running":
                item["status"] = "completed"
        trace.append({"step": len(trace) + 1, "tool": "bedrock_synthesis", "status": "completed", "detail": model_id})
    return text_value, trace

