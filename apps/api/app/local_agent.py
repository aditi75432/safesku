from __future__ import annotations

import json
import os
from typing import Any

from .investigation.agent import SYSTEM_PROMPT, _days_before
from .investigation.store import is_pre_recall_public

try:
    from strands import Agent, tool
    from strands.models.ollama import OllamaModel
except Exception:  # pragma: no cover - optional local runtime dependency
    Agent = None  # type: ignore[assignment]
    OllamaModel = None  # type: ignore[assignment]

    def tool(func):  # type: ignore[no-redef]
        return func


def run_local_agent(store: Any, recall_number: str, query: str) -> tuple[str, list[dict[str, Any]]]:
    """Run the SafeSKU investigator with a locally hosted Ollama model via Strands."""
    if Agent is None or OllamaModel is None:
        raise RuntimeError("Local Strands/Ollama support is not installed")

    model_id = os.getenv("SAFE_SKU_LOCAL_MODEL", "llama3.1")
    host = os.getenv("SAFE_SKU_OLLAMA_HOST", "http://127.0.0.1:11434")
    trace: list[dict[str, Any]] = []

    @tool
    def search_cpsc_recall(number: str) -> str:
        """Retrieve the official CPSC recall record."""
        case = store.find_case(number)
        return json.dumps(case["recall"] if case else {"error": "not found"}, default=str)

    @tool
    def find_amazon_candidates(number: str) -> str:
        """Retrieve ranked marketplace identity candidates."""
        case = store.find_case(number)
        return json.dumps(case.get("amazon_candidates", [])[:8] if case else [], default=str)

    @tool
    def get_saferproducts_incidents(number: str) -> str:
        """Retrieve linked public consumer incidents."""
        case = store.find_case(number)
        return json.dumps(case.get("incidents", []) if case else [], default=str)

    @tool
    def build_safety_timeline(number: str) -> str:
        """Construct the evidence chronology and pre-recall flags."""
        case = store.find_case(number)
        if not case:
            return "[]"
        recall = case["recall"]
        rows: list[dict[str, Any]] = []
        for incident in case.get("incidents", []):
            rows.append({
                "date": incident.get("publication_date") or incident.get("incident_date"),
                "source": "SaferProducts.gov",
                "record_id": incident.get("source_record_id"),
                "pre_recall": is_pre_recall_public(incident, recall.get("recall_date", "")),
            })
        rows.append({"date": recall.get("recall_date"), "source": "CPSC", "record_id": recall.get("source_record_id"), "pre_recall": False})
        return json.dumps(sorted(rows, key=lambda x: x.get("date") or "9999-99-99"), default=str)

    def tool_name(event: Any) -> str:
        use = getattr(event, "tool_use", None)
        if isinstance(use, dict) and use.get("name"):
            return str(use["name"])
        selected = getattr(event, "selected_tool", None)
        return str(getattr(selected, "name", None) or getattr(selected, "__name__", None) or "tool")

    def before_tool(event: Any) -> None:
        trace.append({"step": len(trace) + 1, "tool": tool_name(event), "status": "running"})

    def after_tool(event: Any) -> None:
        name = tool_name(event)
        for item in reversed(trace):
            if item.get("tool") == name and item.get("status") == "running":
                item["status"] = "completed"
                if getattr(event, "duration", None) is not None:
                    item["duration_ms"] = round(float(event.duration) * 1000, 1)
                break

    model = OllamaModel(host=host, model_id=model_id, temperature=0.1)
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[search_cpsc_recall, find_amazon_candidates, get_saferproducts_incidents, build_safety_timeline],
    )
    try:
        from strands.hooks.events import BeforeToolCallEvent, AfterToolCallEvent
        agent.add_hook(BeforeToolCallEvent, before_tool)
        agent.add_hook(AfterToolCallEvent, after_tool)
    except Exception:
        pass

    prompt = f"""{SYSTEM_PROMPT}

Investigation request: {query}
Recall number: {recall_number}

Use the read-only tools to verify the recall, linked marketplace candidates, public incidents,
and the event timeline. Clearly distinguish source facts, identity linkage evidence, and derived
temporal observations. State when human review is required. Never claim causation or that a
pre-recall association predicts a later recall. Cite source record IDs when available.
"""
    result = agent(prompt)
    text_value = getattr(result, "output_text", None) or str(result)
    for item in trace:
        if item.get("status") == "running":
            item["status"] = "completed"
    trace.append({"step": len(trace) + 1, "tool": "local_model_synthesis", "status": "completed", "detail": model_id})
    return text_value, trace
