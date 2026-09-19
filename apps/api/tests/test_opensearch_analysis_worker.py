from __future__ import annotations

import threading

from apps.api.app.workspace.service import WorkspaceService


def test_build_it_analysis_starts_opensearch_index_in_background(monkeypatch, tmp_path):
    service = WorkspaceService(root=tmp_path)
    job_id = "JOB-TEST1234"
    service.store.new_job(job_id, total=0)

    started = threading.Event()

    def fake_index(job: str) -> None:
        assert job == job_id
        started.set()

    monkeypatch.setattr(service, "_index_opensearch", fake_index)
    monkeypatch.setenv("SAFE_SKU_BUILD_IT", "true")
    monkeypatch.setenv("SAFE_SKU_SEARCH_MODE", "opensearch")

    service._run_analysis(job_id)

    assert started.wait(1.0), "OpenSearch indexing worker was not started"
    job = service.job(job_id)
    assert job is not None
    assert job["status"] == "running"
    assert "OpenSearch" in job["message"] or "Preparing" in job["message"]
