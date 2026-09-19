"""Test isolation for the local SafeSKU API.

The production demo can use OpenSearch for retrieval. API tests use their own
temporary stores and therefore intentionally force SQLite search so a developer's
running OpenSearch index cannot leak data between tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_search_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic and independent of the developer's local index."""
    monkeypatch.setenv("SAFE_SKU_SEARCH_MODE", "sqlite")
