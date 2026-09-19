from __future__ import annotations

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
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


RANDOM_SEED = 20260919
TARGET_COLUMN = "review_label"
GROUP_COLUMN = "cpsc_recall_number"

# Keep this list compact because the current development set is small (182 labeled rows).
# These features are derived only from pair content, never from reviewer metadata.
FEATURES = [
    "exact_upc",
    "shared_product_token_count",
    "product_token_jaccard",
    "title_sequence_similarity",
    "amazon_title_token_coverage",
    "cpsc_name_token_coverage_in_title",
    "amazon_brand_in_cpsc_name",
    "cpsc_brand_like_token_in_amazon_title",
    "model_exact_in_title",
    "manufacturer_in_title",
]

LEXICAL_FEATURES = [
    "shared_product_token_count",
    "product_token_jaccard",
    "title_sequence_similarity",
    "amazon_title_token_coverage",
    "cpsc_name_token_coverage_in_title",
]

STOPWORDS = {
    "the", "and", "for", "with", "from", "new", "set", "pack", "of", "to",
    "in", "on", "a", "an", "by", "up", "x", "inch", "inches", "pcs", "piece",
    "pieces", "size", "model", "item", "product", "style", "color", "colour",
}


def norm_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: Any) -> list[str]:
    return [t for t in norm_text(value).split() if t and t not in STOPWORDS]


def token_set(value: Any) -> set[str]:
    return set(tokens(value))


def contains_phrase(haystack: Any, needle: Any) -> bool:
    h = norm_text(haystack)
    n = norm_text(needle)
    return bool(n) and n in h


def safe_ratio(left: Any, right: Any) -> float:
    a = norm_text(left)
    b = norm_text(right)
    if not a or not b:
        return 0.0
    return float(SequenceMatcher(None, a, b).ratio())


def add_text_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    features: list[dict[str, float]] = []

    for row in out.itertuples(index=False):
        cpsc_name = getattr(row, "cpsc_product_name", "")
        amazon_title = getattr(row, "amazon_title", "")
        brand = getattr(row, "amazon_brand", "")
        manufacturer = getattr(row, "amazon_manufacturer", "")
        model = getattr(row, "amazon_model", "")

        cpsc_tokens = token_set(cpsc_name)
        title_tokens = token_set(amazon_title)
        union = cpsc_tokens | title_tokens
        inter = cpsc_tokens & title_tokens

        brand_norm = norm_text(brand)
        manufacturer_norm = norm_text(manufacturer)
        model_norm = norm_text(model)

        # Brand signal is intentionally soft: recall titles often omit the brand,
        # so absence is not evidence of a non-match.
        brand_in_cpsc = float(bool(brand_norm) and brand_norm in norm_text(cpsc_name))

        # "Brand-like" overlap: a normalized brand token appears in the Amazon title.
        brand_tokens = token_set(brand)
        brand_title_overlap = float(bool(brand_tokens & title_tokens))

        model_exact = float(bool(model_norm) and model_norm in norm_text(amazon_title))
        manufacturer_in_title = float(
            bool(manufacturer_norm) and manufacturer_norm in norm_text(amazon_title)
        )

        features.append(
            {
                "title_sequence_similarity": safe_ratio(cpsc_name, amazon_title),
                "amazon_title_token_coverage": float(
                    len(inter) / len(title_tokens) if title_tokens else 0.0
                ),
                "cpsc_name_token_coverage_in_title": float(
                    len(inter) / len(cpsc_tokens) if cpsc_tokens else 0.0
                ),
                "amazon_brand_in_cpsc_name": brand_in_cpsc,
                "cpsc_brand_like_token_in_amazon_title": brand_title_overlap,
                "model_exact_in_title": model_exact,
                "manufacturer_in_title": manufacturer_in_title,
            }
        )

    feature_df = pd.DataFrame(features, index=out.index)
    for col in feature_df.columns:
        out[col] = feature_df[col].astype(float)

    # Use the already-audited blocker features where present.
    for col in ["exact_upc", "shared_product_token_count", "product_token_jaccard"]:
        if col not in out.columns:
            raise ValueError(f"Expected audited candidate feature missing: {col}")
        out[col] = pd.to_numeric(out[col], errors="raise").astype(float)

    return out


def load_labeled_rows(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    if "review_label" not in raw.columns:
        raise ValueError("Input must contain review_label.")

    df = raw[raw[TARGET_COLUMN].isin(["MATCH", "NON_MATCH"])].copy()
    if df.empty:
        raise ValueError("No MATCH/NON_MATCH rows found after excluding UNCERTAIN.")
    if GROUP_COLUMN not in df.columns:
        raise ValueError(f"Missing grouping column: {GROUP_COLUMN}")

    df["target"] = (df[TARGET_COLUMN] == "MATCH").astype(int)
    df = add_text_features(df)
    return df.reset_index(drop=True)


def make_models() -> dict[str, Any]:
    return {
        "logistic_all": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        max_iter=3000,
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
                        max_iter=3000,
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
            l2_regularization=0.75,
            random_state=RANDOM_SEED,
        ),
    }


def metrics(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
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


def rule_predictions(df: pd.DataFrame, rule: str) -> np.ndarray:
    if rule == "upc_only":
        return df["exact_upc"].to_numpy(dtype=int)
    if rule == "token_similarity":
        return (
            ((df["shared_product_token_count"] >= 3) & (df["product_token_jaccard"] >= 0.20))
            | (df["exact_upc"] == 1)
        ).astype(int)
    if rule == "strict_title":
        return (
            (
                (df["product_token_jaccard"] >= 0.30)
                & (df["title_sequence_similarity"] >= 0.45)
            )
            | (df["exact_upc"] == 1)
        ).astype(int)
    raise ValueError(f"Unknown rule: {rule}")


def grouped_model_cv(
    df: pd.DataFrame,
    model_name: str,
    model: Any,
    feature_columns: list[str],
    splits: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    splitter = StratifiedGroupKFold(
        n_splits=splits,
        shuffle=True,
        random_state=RANDOM_SEED,
    )
    X = df[feature_columns]
    y = df["target"].to_numpy()
    groups = df[GROUP_COLUMN].to_numpy()
    oof = np.full(len(df), np.nan, dtype=float)
    fold_records: list[dict[str, Any]] = []

    for fold, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups), start=1):
        fitted = clone(model)
        fitted.fit(X.iloc[train_idx], y[train_idx])
        oof[test_idx] = fitted.predict_proba(X.iloc[test_idx])[:, 1]
        fold_metric = metrics(y[test_idx], oof[test_idx])
        fold_metric.update(
            {
                "fold": fold,
                "train_rows": int(len(train_idx)),
                "test_rows": int(len(test_idx)),
                "train_recalls": int(df.iloc[train_idx][GROUP_COLUMN].nunique()),
                "test_recalls": int(df.iloc[test_idx][GROUP_COLUMN].nunique()),
            }
        )
        fold_records.append(fold_metric)

    if np.isnan(oof).any():
        raise RuntimeError("Grouped CV did not predict every labeled row.")

    overall = metrics(y, oof)
    overall.update(
        {
            "model": model_name,
            "features": feature_columns,
            "folds": fold_records,
        }
    )
    pred = df[["review_id", GROUP_COLUMN, TARGET_COLUMN, "target"]].copy()
    pred["model"] = model_name
    pred["oof_probability_match"] = oof
    pred["oof_prediction"] = (oof >= 0.5).astype(int)
    return overall, pred


def grouped_rule_cv(df: pd.DataFrame, rule: str, splits: int) -> tuple[dict[str, Any], pd.DataFrame]:
    splitter = StratifiedGroupKFold(
        n_splits=splits,
        shuffle=True,
        random_state=RANDOM_SEED,
    )
    X = df[FEATURES]
    y = df["target"].to_numpy()
    groups = df[GROUP_COLUMN].to_numpy()
    pred = np.full(len(df), np.nan)
    fold_records: list[dict[str, Any]] = []

    for fold, (_, test_idx) in enumerate(splitter.split(X, y, groups), start=1):
        test_pred = rule_predictions(df.iloc[test_idx], rule)
        pred[test_idx] = test_pred
        fold_metric = metrics(y[test_idx], test_pred.astype(float))
        fold_metric["fold"] = fold
        fold_records.append(fold_metric)

    overall = metrics(y, pred.astype(int))
    overall.update({"model": rule, "features": list(FEATURES), "folds": fold_records})
    out = df[["review_id", GROUP_COLUMN, TARGET_COLUMN, "target"]].copy()
    out["model"] = rule
    out["oof_probability_match"] = pred
    out["oof_prediction"] = pred.astype(int)
    return overall, out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the leakage-safe Amazon linkage modeling benchmark.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/benchmark/amazon_linkage/amazon_human_review_set_adjudicated.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/benchmark/amazon_linkage/modeling"),
    )
    parser.add_argument("--splits", type=int, default=5)
    args = parser.parse_args()

    if args.splits < 3:
        raise ValueError("--splits must be at least 3")

    raw = pd.read_csv(args.input)
    df = load_labeled_rows(args.input)
    excluded_uncertain = int((raw[TARGET_COLUMN] == "UNCERTAIN").sum())
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("SafeSKU Amazon entity-resolution modeling benchmark")
    print("-------------------------------------------------")
    print(f"Labeled rows: {len(df)}")
    print(f"Excluded UNCERTAIN rows: {excluded_uncertain}")
    print(f"Unique recall groups: {df[GROUP_COLUMN].nunique()}")
    print(f"MATCH: {int(df['target'].sum())}")
    print(f"NON_MATCH: {int((df['target'] == 0).sum())}")
    print(f"CV folds: {args.splits}")
    print()

    results: list[dict[str, Any]] = []
    predictions: list[pd.DataFrame] = []

    for rule in ["upc_only", "token_similarity", "strict_title"]:
        result, pred = grouped_rule_cv(df, rule, args.splits)
        results.append(result)
        predictions.append(pred)

    models = make_models()
    specs = {
        "logistic_all": (models["logistic_all"], FEATURES),
        "logistic_lexical": (models["logistic_lexical"], LEXICAL_FEATURES),
        "hist_gradient_boosting": (models["hist_gradient_boosting"], FEATURES),
    }

    for name, (model, feature_columns) in specs.items():
        result, pred = grouped_model_cv(df, name, model, feature_columns, args.splits)
        results.append(result)
        predictions.append(pred)

    summary = {
        "random_seed": RANDOM_SEED,
        "input": str(args.input),
        "labeled_rows": int(len(df)),
        "excluded_uncertain_rows": excluded_uncertain,
        "recall_groups": int(df[GROUP_COLUMN].nunique()),
        "cv": {
            "strategy": "StratifiedGroupKFold",
            "splits": args.splits,
            "group_column": GROUP_COLUMN,
        },
        "development_label_warning": (
            "Labels are working adjudication from the 200-row review sample and are not an independently "
            "annotated gold-standard dataset. UNCERTAIN rows are excluded."
        ),
        "feature_policy": {
            "all_features": FEATURES,
            "lexical_features": LEXICAL_FEATURES,
            "excluded": [
                "reviewer_notes",
                "adjudication_confidence",
                "adjudicator",
                "labeling_basis",
                "annotation_status",
                "recall identifier",
                "ASIN identifier",
                "dates",
                "selection metadata",
            ],
        },
        "results": results,
    }

    (args.output_dir / "model_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    pd.concat(predictions, ignore_index=True).to_csv(args.output_dir / "oof_predictions.csv", index=False)

    comparison = pd.DataFrame(
        [
            {
                "model": r["model"],
                "precision": r["precision"],
                "recall": r["recall"],
                "f1": r["f1"],
                "false_positive_rate": r["false_positive_rate"],
                "roc_auc": r["roc_auc"],
                "average_precision": r["average_precision"],
            }
            for r in results
        ]
    )
    comparison.to_csv(args.output_dir / "model_comparison.csv", index=False)

    print("OVERALL RESULTS")
    print("----------------")
    for r in results:
        print(
            f"{r['model']}: precision={r['precision']:.3f} "
            f"recall={r['recall']:.3f} f1={r['f1']:.3f} "
            f"fpr={r['false_positive_rate'] if r['false_positive_rate'] is not None else 'NA'}"
        )

    print()
    print(f"Metrics: {args.output_dir / 'model_metrics.json'}")
    print(f"Comparison: {args.output_dir / 'model_comparison.csv'}")
    print(f"OOF predictions: {args.output_dir / 'oof_predictions.csv'}")


if __name__ == "__main__":
    main()
