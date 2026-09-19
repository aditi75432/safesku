from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
OOF_PATH = ROOT / "data/benchmark/amazon_linkage/modeling/oof_predictions.csv"
REVIEW_PATH = ROOT / "data/benchmark/amazon_linkage/amazon_human_review_set_adjudicated.csv"
OUT_DIR = ROOT / "data/benchmark/amazon_linkage/modeling"

THRESHOLDS = [round(x / 20, 2) for x in range(2, 20)]  # 0.10 ... 0.95
TOP_KS = (1, 3, 5, 10)


def binary_metrics(y_true: pd.Series, y_prob: pd.Series, threshold: float) -> dict[str, float]:
    pred = (y_prob >= threshold).astype(int)
    tp = int(((y_true == 1) & (pred == 1)).sum())
    fp = int(((y_true == 0) & (pred == 1)).sum())
    fn = int(((y_true == 1) & (pred == 0)).sum())
    tn = int(((y_true == 0) & (pred == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "threshold": threshold,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def group_top_k_hit_rate(
    frame: pd.DataFrame,
    ks: Iterable[int] = TOP_KS,
) -> dict[str, float]:
    """Hit rate among recall groups that contain at least one reviewed MATCH.

    Important: this is measured only inside the 182 labeled review rows.
    It is not a recall estimate for the full 84,037-candidate population.
    """
    positives = frame.loc[frame["target"] == 1, "cpsc_recall_number"].nunique()
    if positives == 0:
        return {f"top_{k}_hit_rate": 0.0 for k in ks}

    hits = {k: 0 for k in ks}
    for _, group in frame.groupby("cpsc_recall_number", sort=False):
        if not (group["target"] == 1).any():
            continue
        ranked = group.sort_values(
            ["oof_probability_match", "review_id"], ascending=[False, True]
        )
        target = ranked["target"].tolist()
        for k in ks:
            if any(target[:k]):
                hits[k] += 1

    return {f"top_{k}_hit_rate": hits[k] / positives for k in ks}


def main() -> None:
    if not OOF_PATH.exists():
        raise FileNotFoundError(f"Missing OOF predictions: {OOF_PATH}")

    oof = pd.read_csv(OOF_PATH)
    required = {
        "review_id",
        "cpsc_recall_number",
        "target",
        "model",
        "oof_probability_match",
    }
    missing = required - set(oof.columns)
    if missing:
        raise ValueError(f"OOF predictions missing columns: {sorted(missing)}")

    labels_path = REVIEW_PATH
    if not labels_path.exists():
        fallback = ROOT / "data/benchmark/amazon_linkage/amazon_human_review_set.csv"
        if fallback.exists():
            labels_path = fallback
        else:
            raise FileNotFoundError(
                "Missing adjudicated Amazon review set. Expected "
                f"{REVIEW_PATH} or {fallback}."
            )

    labels = pd.read_csv(labels_path)
    if "review_label" in labels.columns:
        labeled = labels.loc[labels["review_label"].isin(["MATCH", "NON_MATCH"]), [
            "review_id",
            "cpsc_recall_number",
            "review_label",
        ]].copy()
        labeled["target_from_label"] = (labeled["review_label"] == "MATCH").astype(int)
    else:
        raise ValueError("Review set must contain review_label.")

    # Join labels back to OOF predictions. Prefer the adjudicated label when present.
    merged = oof.merge(
        labeled[["review_id", "target_from_label"]], on="review_id", how="inner"
    )
    merged["target"] = merged["target_from_label"].astype(int)
    merged["cpsc_recall_number"] = merged["cpsc_recall_number"].astype(int)
    merged["oof_probability_match"] = pd.to_numeric(
        merged["oof_probability_match"], errors="raise"
    )

    threshold_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for model_name, frame in merged.groupby("model", sort=True):
        frame = frame.sort_values(["cpsc_recall_number", "review_id"]).copy()

        y_true = frame["target"]
        y_prob = frame["oof_probability_match"]
        try:
            auroc = float(roc_auc_score(y_true, y_prob))
        except ValueError:
            auroc = 0.0
        try:
            auprc = float(average_precision_score(y_true, y_prob))
        except ValueError:
            auprc = 0.0

        for threshold in THRESHOLDS:
            metrics = binary_metrics(y_true, y_prob, threshold)
            threshold_rows.append(
                {
                    "model": model_name,
                    "metric_scope": "pair_level_oof",
                    "n_rows": len(frame),
                    "n_recall_groups": frame["cpsc_recall_number"].nunique(),
                    "n_positive_rows": int(y_true.sum()),
                    "n_negative_rows": int((y_true == 0).sum()),
                    "auroc": auroc,
                    "auprc": auprc,
                    **metrics,
                }
            )

        group_metrics = group_top_k_hit_rate(frame)
        summary_rows.append(
            {
                "model": model_name,
                "n_rows": len(frame),
                "n_recall_groups": frame["cpsc_recall_number"].nunique(),
                "n_positive_rows": int(y_true.sum()),
                "n_positive_recall_groups": int(
                    frame.loc[y_true == 1, "cpsc_recall_number"].nunique()
                ),
                "auroc": auroc,
                "auprc": auprc,
                **group_metrics,
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    threshold_path = OUT_DIR / "threshold_sweep.csv"
    summary_path = OUT_DIR / "group_ranking_summary.json"
    pd.DataFrame(threshold_rows).to_csv(threshold_path, index=False)
    summary_path.write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")

    print("SafeSKU Amazon linkage threshold + group-ranking analysis")
    print("----------------------------------------------------------")
    print(f"Labeled OOF rows: {merged['review_id'].nunique()}")
    print(f"Models: {', '.join(sorted(merged['model'].unique()))}")
    print("\nPAIR-LEVEL OOF SUMMARY")
    print("----------------------")
    for row in summary_rows:
        print(
            f"{row['model']}: AUROC={row['auroc']:.3f} "
            f"AUPRC={row['auprc']:.3f} "
            f"Top-1={row['top_1_hit_rate']:.3f} "
            f"Top-3={row['top_3_hit_rate']:.3f} "
            f"Top-5={row['top_5_hit_rate']:.3f} "
            f"Top-10={row['top_10_hit_rate']:.3f}"
        )

    print("\nTHRESHOLD SWEEP")
    print("---------------")
    for model_name in sorted(merged["model"].unique()):
        model_rows = [r for r in threshold_rows if r["model"] == model_name]
        best_f1 = max(model_rows, key=lambda r: (r["f1"], r["precision"], r["recall"]))
        print(
            f"{model_name}: best observed OOF F1={best_f1['f1']:.3f} "
            f"at threshold={best_f1['threshold']:.2f}; "
            f"precision={best_f1['precision']:.3f}; recall={best_f1['recall']:.3f}; "
            f"fpr={best_f1['fpr']:.3f}"
        )

    print("\nArtifacts:")
    print(f"Threshold sweep: {threshold_path}")
    print(f"Group ranking:   {summary_path}")
    print("\nNOTE: thresholds are exploratory on development OOF predictions. "
          "Do not report a selected threshold as an unbiased test-set result.")


if __name__ == "__main__":
    main()
