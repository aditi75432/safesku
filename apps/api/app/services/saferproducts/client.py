from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class SaferProductsPage:
    records: list[dict[str, Any]]
    next_url: str | None


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
        top: int = 1,
        skip: int = 0,
        filter_expression: str | None = None,
    ) -> SaferProductsPage:
        params: dict[str, str | int] = {
            "$format": "json",
            "$top": top,
            "$skip": skip,
        }

        if filter_expression:
            params["$filter"] = filter_expression

        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            response = client.get(
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
        else:
            records = data
            next_url = None

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

        return SaferProductsPage(
            records=normalized_records,
            next_url=next_url if isinstance(next_url, str) else None,
        )
