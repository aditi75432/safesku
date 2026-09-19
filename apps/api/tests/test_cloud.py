from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def test_cloud_config_is_disabled_by_default(monkeypatch):
    from app import demo_app

    monkeypatch.delenv("SAFE_SKU_CLOUD_MODE", raising=False)
    client = TestClient(demo_app.app)
    response = client.get("/api/cloud/config")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_cloud_presign_uses_workspace_helper(monkeypatch):
    from app import demo_app

    class FakeCloudWorkspace:
        def presign_bundle(self, filename: str, size_bytes: int):
            return {"upload_id": "UP-TEST", "key": "incoming/UP-TEST/demo.zip", "url": "https://example.invalid", "size_bytes": size_bytes}

    monkeypatch.setenv("SAFE_SKU_CLOUD_MODE", "true")
    monkeypatch.setattr(demo_app, "cloud_workspace", FakeCloudWorkspace())

    client = TestClient(demo_app.app)
    response = client.post("/api/cloud/uploads/presign?filename=demo.zip&size_bytes=123")
    assert response.status_code == 200
    assert response.json()["upload"]["upload_id"] == "UP-TEST"
    assert response.json()["upload"]["size_bytes"] == 123
