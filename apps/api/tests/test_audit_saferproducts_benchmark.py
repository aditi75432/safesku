from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_saferproducts_benchmark import iter_raw_records


def test_iter_raw_records_matches_actual_raw_layout(tmp_path: Path) -> None:
    window_dir = tmp_path / "2020-01-01"
    window_dir.mkdir()

    payload = {
        "d": {
            "results": [
                {"IncidentReportNumber": "A"},
                {"IncidentReportNumber": "B"},
            ]
        }
    }

    (window_dir / "page_00001.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    records = list(iter_raw_records(tmp_path))

    assert len(records) == 2
    assert records[0][2]["IncidentReportNumber"] == "A"
    assert records[1][2]["IncidentReportNumber"] == "B"
