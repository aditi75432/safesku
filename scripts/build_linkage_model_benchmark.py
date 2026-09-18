from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


RANDOM_SEED = 20260918

FEATURES_ALL = [
    "exact_upc",
    "shared_product_token_count",
    "product_token_jaccard",
    "product_name_sequence_similarity",
    "cpsc_name_token_coverage",
    "incident_name_token_coverage",
    "incident_brand_in_cpsc_name",
    "incident_model_in_cpsc_name",
    "manufacturer_in_cpsc_name",
]

FEATURES_LEXICAL = [
    "shared_product_token_count",
    "product_token_jaccard",
    "product_name_sequence_similarity",
    "cpsc_name_token_coverage",
    "incident_name_token_coverage",
]

TARGET_COLUMN = "review_label"
GROUP_COLUMN = "cpsc_recall_number"


def load_labeled_rows(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    required = {
        TARGET_COLUMN,
        GROUP_COLUMN,
        *FEATURES_ALL,
        "review_id",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df[df[TARGET_COLUMN].isin(["MATCH", "NON_MATCH"])].copy()
    if df.empty:
        raise ValueError("No MATCH/NON_MATCH rows found.")

    # UNCERTAIN rows are intentionally excluded from supervised training/evaluation.
    df["target"] = (df[TARGET_COLUMN] == "MATCH").astype(int)

    # Feature columns are numeric in the benchmark. Failing loudly is preferable
    # to silently coercing malformed values into zeros.
    for col in FEATURES_ALL:
        df[col] = pd.to_numeric(df[col], errors="raise")

    if df[GROUP_COLUMN].isna().any():
        raise ValueError("Each labeled row must have a CPSC recall number for grouped evaluation.")

    return df.reset_index(drop=True)


def make_models() -> dict[str, Any]:
    return {
        "logistic_all": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                    ),
                ),
            ]
        ),
        "logistic_lexical": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                    ),
                ),
            ]
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=150,
            learning_rate=0.05,
            max_leaf_nodes=7,
            l2_regularization=0.5,
            random_state=RANDOM_SEED,
        ),
    }


def evaluate_predictions(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    result: dict[str, Any] = {
        "n": int(len(y_true)),
        "positives": int(y_true.sum()),
        "negatives": int(len(y_true) - y_true.sum()),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else None,
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
    }

    if len(np.unique(y_true)) == 2:
        result["roc_auc"] = float(roc_auc_score(y_true, y_prob))
        result["average_precision"] = float(average_precision_score(y_true, y_prob))
    else:
        result["roc_auc"] = None
        result["average_precision"] = None

    return result


def evaluate_rule(y_true: np.ndarray, df_fold: pd.DataFrame, rule: str) -> np.ndarray:
    if rule == "upc_only":
        return df_fold["exact_upc"].to_numpy(dtype=int)
    if rule == "token_and_similarity":
        # A transparent non-learning baseline: require both meaningful token overlap
        # and reasonably strong whole-name similarity.
        return (
            (
                (df_fold["shared_product_token_count"] >= 3)
                & (df_fold["product_token_jaccard"] >= 0.20)
            )
            | (df_fold["exact_upc"] == 1)
        ).astype(int)
    raise ValueError(f"Unknown rule: {rule}")


def run_grouped_cv(
    df: pd.DataFrame,
    model_name: str,
    model: Any,
    feature_columns: list[str],
    splits: int = 5,
) -> tuple[dict[str, Any], pd.DataFrame]:
    splitter = StratifiedGroupKFold(
        n_splits=splits,
        shuffle=True,
        random_state=RANDOM_SEED,
    )

    oof_prob = np.full(len(df), np.nan, dtype=float)
    fold_records: list[dict[str, Any]] = []

    X = df[feature_columns]
    y = df["target"].to_numpy()
    groups = df[GROUP_COLUMN].to_numpy()

    for fold, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups), start=1):
        fitted = clone(model)
        fitted.fit(X.iloc[train_idx], y[train_idx])
        oof_prob[test_idx] = fitted.predict_proba(X.iloc[test_idx])[:, 1]

        fold_metrics = evaluate_predictions(y[test_idx], oof_prob[test_idx])
        fold_metrics["fold"] = fold
        fold_metrics["train_rows"] = int(len(train_idx))
        fold_metrics["test_rows"] = int(len(test_idx))
        fold_metrics["train_recalls"] = int(df.iloc[train_idx][GROUP_COLUMN].nunique())
        fold_metrics["test_recalls"] = int(df.iloc[test_idx][GROUP_COLUMN].nunique())
        fold_records.append(fold_metrics)

    if np.isnan(oof_prob).any():
        raise RuntimeError("Grouped CV did not produce a prediction for every row.")

    overall = evaluate_predictions(y, oof_prob)
    overall["model"] = model_name
    overall["features"] = feature_columns
    overall["folds"] = fold_records

    predictions = df[
        [
            "review_id",
            GROUP_COLUMN,
            TARGET_COLUMN,
            "target",
            "temporal_status",
            "similarity_band",
        ]
    ].copy()
    predictions["model"] = model_name
    predictions["oof_probability_match"] = oof_prob
    predictions["oof_prediction"] = (oof_prob >= 0.5).astype(int)

    return overall, predictions


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate leakage-safe product linkage models.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/benchmark/linkage/human_review_set_adjudicated.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/benchmark/linkage/modeling"),
    )
    parser.add_argument("--splits", type=int, default=5)
    args = parser.parse_args()

    if args.splits < 3:
        raise ValueError("--splits must be at least 3")

    raw_df = pd.read_csv(args.input)
    df = load_labeled_rows(args.input)
    excluded_uncertain_rows = int(len(raw_df) - len(df))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("SafeSKU entity-resolution modeling benchmark")
    print("--------------------------------------------")
    print(f"Labeled rows: {len(df)}")
    print(f"Excluded UNCERTAIN rows: {excluded_uncertain_rows}")
    print(f"Unique recall groups: {df[GROUP_COLUMN].nunique()}")
    print(f"MATCH: {(df['target'] == 1).sum()}")
    print(f"NON_MATCH: {(df['target'] == 0).sum()}")
    print(f"CV folds: {args.splits}")
    print()

    results: list[dict[str, Any]] = []
    all_predictions: list[pd.DataFrame] = []

    # Non-learning baselines are evaluated out-of-fold too so their comparison
    # is directly aligned with the learned models' test rows.
    splitter = StratifiedGroupKFold(
        n_splits=args.splits,
        shuffle=True,
        random_state=RANDOM_SEED,
    )
    y = df["target"].to_numpy()
    groups = df[GROUP_COLUMN].to_numpy()

    rule_predictions: dict[str, np.ndarray] = {
        "upc_only": np.full(len(df), np.nan),
        "token_and_similarity": np.full(len(df), np.nan),
    }

    fold_rule_results: dict[str, list[dict[str, Any]]] = {"upc_only": [], "token_and_similarity": []}

    X = df[FEATURES_ALL]
    for fold, (_, test_idx) in enumerate(splitter.split(X, y, groups), start=1):
        for rule in rule_predictions:
            pred = evaluate_rule(y[test_idx], df.iloc[test_idx], rule)
            rule_predictions[rule][test_idx] = pred
            metrics = evaluate_predictions(y[test_idx], pred.astype(float))
            metrics["fold"] = fold
            fold_rule_results[rule].append(metrics)

    for rule, pred in rule_predictions.items():
        metrics = evaluate_predictions(y, pred.astype(int))
        metrics["model"] = rule
        metrics["features"] = (
            ["exact_upc"]
            if rule == "upc_only"
            else ["exact_upc", "shared_product_token_count", "product_token_jaccard", "product_name_sequence_similarity"]
        )
        metrics["folds"] = fold_rule_results[rule]
        results.append(metrics)

        pred_df = df[["review_id", GROUP_COLUMN, TARGET_COLUMN, "target", "temporal_status", "similarity_band"]].copy()
        pred_df["model"] = rule
        pred_df["oof_probability_match"] = pred
        pred_df["oof_prediction"] = pred.astype(int)
        all_predictions.append(pred_df)

    model_specs = make_models()
    specs = {
        "logistic_all": (model_specs["logistic_all"], FEATURES_ALL),
        "logistic_lexical": (model_specs["logistic_lexical"], FEATURES_LEXICAL),
        "hist_gradient_boosting": (model_specs["hist_gradient_boosting"], FEATURES_ALL),
    }

    for name, (model, features) in specs.items():
        metrics, predictions = run_grouped_cv(
            df=df,
            model_name=name,
            model=model,
            feature_columns=features,
            splits=args.splits,
        )
        results.append(metrics)
        all_predictions.append(predictions)

    summary = {
        "random_seed": RANDOM_SEED,
        "input": str(args.input),
        "labeled_rows": int(len(df)),
        "excluded_uncertain_rows": excluded_uncertain_rows,
        "recall_groups": int(df[GROUP_COLUMN].nunique()),
        "cv": {
            "strategy": "StratifiedGroupKFold",
            "splits": args.splits,
            "group_column": GROUP_COLUMN,
            "stratification_target": TARGET_COLUMN,
        },
        "feature_policy": {
            "all_features": FEATURES_ALL,
            "lexical_features": FEATURES_LEXICAL,
            "excluded": [
                "recall identifiers",
                "dates",
                "temporal_status",
                "selection_reason",
                "reviewer_notes",
                "annotation metadata",
                "source URLs",
            ],
        },
        "results": results,
    }

    (args.output_dir / "model_metrics.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    pd.concat(all_predictions, ignore_index=True).to_csv(
        args.output_dir / "oof_predictions.csv",
        index=False,
    )

    comparison = []
    for item in results:
        comparison.append(
            {
                "model": item["model"],
                "precision": item["precision"],
                "recall": item["recall"],
                "f1": item["f1"],
                "false_positive_rate": item["false_positive_rate"],
                "roc_auc": item["roc_auc"],
                "average_precision": item["average_precision"],
            }
        )
    pd.DataFrame(comparison).to_csv(args.output_dir / "model_comparison.csv", index=False)

    print("OVERALL RESULTS")
    print("----------------")
    for item in results:
        print(
            f"{item['model']}: "
            f"precision={item['precision']:.3f} "
            f"recall={item['recall']:.3f} "
            f"f1={item['f1']:.3f} "
            f"fpr={item['false_positive_rate'] if item['false_positive_rate'] is not None else 'NA'}"
        )

    print()
    print(f"Metrics: {args.output_dir / 'model_metrics.json'}")
    print(f"Comparison: {args.output_dir / 'model_comparison.csv'}")
    print(f"OOF predictions: {args.output_dir / 'oof_predictions.csv'}")


if __name__ == "__main__":
    main()
