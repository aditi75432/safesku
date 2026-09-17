from __future__ import annotations
from typing import Any
import httpx

class CPSCClient:
    """HTTP client for the official CPSC Recall REST service."""
    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search_recalls(self, *, start_date: str | None = None,
                       end_date: str | None = None,
                       product_name: str | None = None,
                       hazard: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"format": "json"}
        if start_date:
            params["RecallDateStart"] = start_date
        if end_date:
            params["RecallDateEnd"] = end_date
        if product_name:
            params["ProductName"] = product_name
        if hazard:
            params["Hazard"] = hazard

        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()

        if payload is None:
            return []
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("Recalls", "recalls", "Recall", "recall", "value"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    return [value]
            return [payload]
        raise ValueError(f"Unexpected CPSC response type: {type(payload).__name__}")
