import os


def test_build_it_stack_status(monkeypatch):
    monkeypatch.setenv("SAFE_SKU_BUILD_IT", "true")
    from app.buildit import build_it_enabled, stack_status

    assert build_it_enabled() is True
    status = stack_status()
    assert status["track"] == "build_it"
    assert status["policy"] == "cedar"
    assert status["sam_local"] is True
