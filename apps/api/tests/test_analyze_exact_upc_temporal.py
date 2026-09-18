from __future__ import annotations

from scripts.analyze_exact_upc_temporal import classify_temporal_status


def test_pre_recall_public() -> None:
    row = {
        "cpsc_recall_date": "2022-06-30",
        "incident_date": "2021-10-18",
        "publication_date": "2021-11-10",
    }
    assert classify_temporal_status(row) == "pre_recall_public"


def test_incident_before_recall_but_published_after() -> None:
    row = {
        "cpsc_recall_date": "2020-12-23",
        "incident_date": "2020-09-10",
        "publication_date": "2021-02-04",
    }
    assert (
        classify_temporal_status(row)
        == "pre_incident_published_after_recall"
    )


def test_incident_on_recall_date_is_not_pre_recall() -> None:
    row = {
        "cpsc_recall_date": "2021-08-04",
        "incident_date": "2021-08-04",
        "publication_date": "2021-10-29",
    }
    assert classify_temporal_status(row) == "incident_on_or_after_recall"
