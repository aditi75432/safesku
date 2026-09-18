from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class SaferProductsPage:
    records: list[dict[str, Any]]
    next_url: str | None
    total_count: int | None
    raw_payload: dict[str, Any]


class SaferProductsClient:
    """HTTP client for the official SaferProducts.gov OData incident API."""

    def __init__(
        self,
        base_url: str,
        application_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not application_key.strip():
            raise ValueError("SaferProducts application key must not be empty.")

        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.auth = httpx.BasicAuth(application_key, "")

    def fetch_page(
        self,
        *,
        top: int = 100,
        skip: int = 0,
        filter_expression: str | None = None,
        order_by: str | None = None,
        inline_count: bool = False,
    ) -> SaferProductsPage:
        if top <= 0:
            raise ValueError("top must be positive.")
        if skip < 0:
            raise ValueError("skip cannot be negative.")

        params: dict[str, str | int] = {
            "$format": "json",
            "$top": top,
            "$skip": skip,
        }

        if filter_expression:
            params["$filter"] = filter_expression
        if order_by:
            params["$orderby"] = order_by
        if inline_count:
            params["$inlinecount"] = "allpages"

        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as http_client:
            response = http_client.get(
                f"{self.base_url}/IncidentDetails",
                params=params,
                auth=self.auth,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()

        return self._parse_page(payload)

    @staticmethod
    def _parse_page(payload: Any) -> SaferProductsPage:
        if not isinstance(payload, dict):
            raise ValueError(
                f"Unexpected SaferProducts response type: {type(payload).__name__}"
            )

        data = payload.get("d", payload)

        if isinstance(data, dict):
            records = data.get("results")
            next_url = data.get("__next") or data.get("odata.nextLink")
            raw_count = data.get("__count") or data.get("odata.count")
        else:
            records = data
            next_url = None
            raw_count = None

        if records is None:
            records = payload.get("value")
        if records is None:
            records = []
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            raise ValueError(
                "Unexpected SaferProducts records structure: "
                f"{type(records).__name__}"
            )

        normalized_records = [
            record for record in records if isinstance(record, dict)
        ]

        total_count: int | None = None
        if raw_count not in (None, ""):
            try:
                total_count = int(raw_count)
            except (TypeError, ValueError):
                total_count = None

        return SaferProductsPage(
            records=normalized_records,
            next_url=next_url if isinstance(next_url, str) else None,
            total_count=total_count,
            raw_payload=payload,
        )
