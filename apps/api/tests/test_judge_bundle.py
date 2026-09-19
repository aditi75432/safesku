from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "build_safesku_judge_bundle.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_judge_bundle", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_product_slice_extracts_only_candidate_asins(tmp_path: Path):
    module = _load_module()
    candidates = tmp_path / "candidates.jsonl"
    source = tmp_path / "products.jsonl"
    output = tmp_path / "slice.jsonl"

    candidates.write_text(
        json.dumps({"amazon_parent_asin": "B001"}) + "\n"
        + json.dumps({"amazon_parent_asin": "B002"}) + "\n",
        encoding="utf-8",
    )
    source.write_text(
        json.dumps({"parent_asin": "B000", "title": "ignore"}) + "\n"
        + json.dumps({"parent_asin": "B002", "title": "keep"}) + "\n"
        + json.dumps({"parent_asin": "B001", "title": "keep"}) + "\n"
        + json.dumps({"parent_asin": "B001", "title": "duplicate"}) + "\n",
        encoding="utf-8",
    )

    matched, missing = module.build_product_slice(source, candidates, output)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert matched == 2
    assert missing == 0
    assert {row["parent_asin"] for row in rows} == {"B001", "B002"}
    assert len(rows) == 2
