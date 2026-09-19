from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.analyze_amazon_linkage_thresholds import binary_metrics, group_top_k_hit_rate


def test_binary_metrics_balanced_case():
    y_true = pd.Series([1, 1, 0, 0])
    y_prob = pd.Series([0.9, 0.8, 0.7, 0.1])
    out = binary_metrics(y_true, y_prob, 0.75)
    assert out["tp"] == 2
    assert out["fp"] == 0
    assert out["fn"] == 0
    assert out["tn"] == 2
    assert out["precision"] == 1.0
    assert out["recall"] == 1.0


def test_group_top_k_hit_rate():
    # Group 1: positive is ranked second; Group 2: positive is ranked first.
    # Therefore Top-1 retrieves one of two positive groups, while Top-2
    # retrieves both.
    df = pd.DataFrame(
        {
            "cpsc_recall_number": [1, 1, 2, 2],
            "target": [0, 1, 0, 1],
            "oof_probability_match": [0.9, 0.2, 0.8, 0.9],
            "review_id": ["a", "b", "c", "d"],
        }
    )
    out = group_top_k_hit_rate(df, ks=(1, 2))
    assert out["top_1_hit_rate"] == 0.5
    assert out["top_2_hit_rate"] == 1.0
