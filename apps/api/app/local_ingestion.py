"""Local-only ingestion worker for SafeSKU Build It.

SAM Local should return the HTTP response as soon as a bundle is registered.
Long-running SQLite ingestion must therefore not run as FastAPI BackgroundTasks:
under the Lambda adapter those tasks remain part of the invocation lifecycle and
can exhaust the function timeout before the HTTP response is completed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable

_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="safesku-ingest")


def _run(workspace: Any, dataset_ids: Iterable[str]) -> None:
    # Keep bundle ingestion sequential. WorkspaceStore uses SQLite/WAL and each
    # dataset updates the same database; one worker avoids unnecessary write locks.
    for dataset_id in dataset_ids:
        workspace.ingest_dataset(dataset_id)


def submit_ingestion(workspace: Any, dataset_ids: Iterable[str]) -> bool:
    ids = [str(dataset_id) for dataset_id in dataset_ids if dataset_id]
    if not ids:
        return False
    _EXECUTOR.submit(_run, workspace, ids)
    return True
