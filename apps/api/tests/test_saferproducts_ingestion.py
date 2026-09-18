from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.saferproducts.client import SaferProductsClient, SaferProductsPage
from app.services.saferproducts.ingestion import (
    ingest_window,
    iter_month_windows,
    load_raw_window,
)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def fetch_page(
        self,
        *,
        top: int,
        skip: int,
        **_: object,
    ) -> SaferProductsPage:
        self.calls.append(skip)
        all_ids = [f"INC-{i:03d}" for i in range(120)]
        page_ids = all_ids[skip : skip + 50]

        records = [
            {
                "IncidentReportNumber": incident_id,
                "IncidentDate": "2020-01-01",
            }
            for incident_id in page_ids
        ]

        return SaferProductsPage(
            records=records,
            next_url=None,
            total_count=120,
            raw_payload={
                "d": {
                    "results": records,
                    "__count": "120",
                }
            },
        )


def test_iter_month_windows() -> None:
    assert iter_month_windows(
        date(2020, 1, 15),
        date(2020, 3, 10),
    ) == [
        (date(2020, 1, 15), date(2020, 2, 1)),
        (date(2020, 2, 1), date(2020, 3, 1)),
        (date(2020, 3, 1), date(2020, 3, 10)),
    ]


def test_load_raw_window_reads_existing_pages(tmp_path: Path) -> None:
    window_root = tmp_path / "2020-01-01"
    window_root.mkdir()

    records = [
        {
            "IncidentReportNumber": f"INC-{i:03d}",
            "IncidentDate": "2020-01-01",
        }
        for i in range(50)
    ]

    payload = {
        "d": {
            "results": records,
            "__count": "120",
        }
    }

    (window_root / "page_00001.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    state = load_raw_window(window_root)

    assert len(state.records) == 50
    assert state.expected_total == 120
    assert state.page_count == 1


def test_ingest_window_resumes_from_existing_records(tmp_path: Path) -> None:
    client = FakeClient()
    raw_root = tmp_path / "raw"
    window_root = raw_root / "2020-01-01"
    window_root.mkdir(parents=True)

    for page_number, start in ((1, 0), (2, 50)):
        records = [
            {
                "IncidentReportNumber": f"INC-{i:03d}",
                "IncidentDate": "2020-01-01",
            }
            for i in range(start, start + 50)
        ]

        payload = {
            "d": {
                "results": records,
                "__count": "120" if page_number == 1 else None,
            }
        }

        (window_root / f"page_{page_number:05d}.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    state = load_raw_window(window_root)

    result, normalized = ingest_window(
        client,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 2, 1),
        raw_root=raw_root,
        page_size=100,
        sleep_seconds=0,
        existing_state=state,
        log=lambda _: None,
    )

    assert client.calls == [100]
    assert result.resumed_from_skip == 100
    assert result.raw_records == 120
    assert len(normalized) == 120
    assert result.reused_raw_pages is True


def test_client_parse_still_returns_page_object() -> None:
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

    page = SaferProductsClient._parse_page(payload)

    assert len(page.records) == 1
    assert page.total_count == 123
    assert page.next_url == "https://example.test/next"
