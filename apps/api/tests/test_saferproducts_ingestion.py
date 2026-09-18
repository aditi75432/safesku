from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from app.services.saferproducts.client import SaferProductsPage
from app.services.saferproducts.ingestion import (
    build_filter,
    ingest_window,
    iter_month_windows,
)


class FakeSaferProductsClient:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.pages = [
            [f"INC-{i:03d}" for i in range(50)],
            [f"INC-{i:03d}" for i in range(50, 100)],
            [f"INC-{i:03d}" for i in range(100, 150)],
            [f"INC-{i:03d}" for i in range(150, 200)],
            [f"INC-{i:03d}" for i in range(200, 250)],
            [f"INC-{i:03d}" for i in range(250, 277)],
        ]

    def fetch_page(
        self,
        *,
        top: int,
        skip: int,
        **_: Any,
    ) -> SaferProductsPage:
        self.calls.append(skip)

        page_index = skip // 50
        records = [
            {
                "IncidentReportNumber": incident_id,
                "IncidentDate": "2020-01-01",
            }
            for incident_id in self.pages[page_index]
        ]

        return SaferProductsPage(
            records=records,
            next_url=None,
            total_count=277,
            raw_payload={
                "d": {
                    "results": records,
                    "__count": "277",
                }
            },
        )


def test_iter_month_windows_inclusive_start_exclusive_end() -> None:
    windows = iter_month_windows(
        date(2020, 1, 15),
        date(2020, 3, 10),
    )

    assert windows == [
        (date(2020, 1, 15), date(2020, 2, 1)),
        (date(2020, 2, 1), date(2020, 3, 1)),
        (date(2020, 3, 1), date(2020, 3, 10)),
    ]


def test_build_filter() -> None:
    assert build_filter(
        date(2020, 1, 1),
        date(2020, 2, 1),
    ) == (
        "IncidentDate ge datetime'2020-01-01T00:00:00' "
        "and IncidentDate lt datetime'2020-02-01T00:00:00'"
    )


def test_ingest_window_uses_actual_returned_page_size() -> None:
    client = FakeSaferProductsClient()
    raw_root = Path("test-output-saferproducts-raw")

    result, normalized = ingest_window(
        client,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 2, 1),
        raw_root=raw_root,
        page_size=100,
        sleep_seconds=0,
        log=lambda _: None,
    )

    try:
        assert result.pages_fetched == 6
        assert result.raw_records == 277
        assert result.normalized_records == 277
        assert result.rejected_records == 0
        assert len(normalized) == 277

        # The API returned 50 records per request despite top=100.
        assert client.calls == [0, 50, 100, 150, 200, 250]
    finally:
        import shutil

        shutil.rmtree(raw_root, ignore_errors=True)


def test_client_page_object_preserves_metadata() -> None:
    payload = {
        "d": {
            "__count": "123",
            "results": [
                {
                    "IncidentReportNumber": "20200101-TEST",
                    "IncidentDate": "1/2/2020",
                }
            ],
            "__next": "https://example.test/next",
        }
    }

    from app.services.saferproducts.client import SaferProductsClient

    page = SaferProductsClient._parse_page(payload)

    assert len(page.records) == 1
    assert page.records[0]["IncidentReportNumber"] == "20200101-TEST"
    assert page.next_url == "https://example.test/next"
    assert page.total_count == 123
    assert page.raw_payload == payload
