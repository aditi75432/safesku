from __future__ import annotations

import time

from app.local_ingestion import submit_ingestion


def test_submit_ingestion_returns_without_waiting():
    seen: list[str] = []

    class FakeWorkspace:
        def ingest_dataset(self, dataset_id: str) -> None:
            time.sleep(0.25)
            seen.append(dataset_id)

    started = time.perf_counter()
    assert submit_ingestion(FakeWorkspace(), ["D1"]) is True
    elapsed = time.perf_counter() - started

    assert elapsed < 0.15
    deadline = time.perf_counter() + 2
    while time.perf_counter() < deadline and seen != ["D1"]:
        time.sleep(0.02)
    assert seen == ["D1"]


def test_submit_ingestion_empty_list():
    class FakeWorkspace:
        def ingest_dataset(self, dataset_id: str) -> None:
            raise AssertionError("should not run")

    assert submit_ingestion(FakeWorkspace(), []) is False
