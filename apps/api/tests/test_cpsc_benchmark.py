from __future__ import annotations

from datetime import date

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_cpsc_benchmark import add_months, iter_date_windows  # noqa: E402


def test_add_months_clamps_to_valid_day() -> None:
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 11, 30), 2) == date(2024, 1, 30)


def test_iter_date_windows_covers_range_without_gaps() -> None:
    windows = list(
        iter_date_windows(
            date(2020, 1, 1),
            date(2020, 9, 15),
            3,
        )
    )

    assert windows == [
        (date(2020, 1, 1), date(2020, 3, 31)),
        (date(2020, 4, 1), date(2020, 6, 30)),
        (date(2020, 7, 1), date(2020, 9, 15)),
    ]


def test_iter_date_windows_rejects_invalid_range() -> None:
    try:
        list(iter_date_windows(date(2024, 2, 1), date(2024, 1, 31), 3))
    except ValueError as exc:
        assert "start_date" in str(exc)
    else:
        raise AssertionError("Expected invalid date range to raise ValueError")
