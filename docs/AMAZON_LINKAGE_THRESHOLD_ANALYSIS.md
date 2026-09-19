# Amazon Linkage Threshold + Group Ranking Analysis

This experiment evaluates the existing out-of-fold (OOF) Amazon entity-resolution probabilities across a threshold grid and measures recall-group retrieval inside the labeled review sample.

## Inputs

- `data/benchmark/amazon_linkage/modeling/oof_predictions.csv`
- `data/benchmark/amazon_linkage/amazon_human_review_set_adjudicated.csv`
  - falls back to the non-adjudicated review CSV only if the adjudicated file is unavailable

## Outputs

- `data/benchmark/amazon_linkage/modeling/threshold_sweep.csv`
- `data/benchmark/amazon_linkage/modeling/group_ranking_summary.json`

## Why this matters

SafeSKU is a candidate-ranking/linkage problem, not only a binary classification problem. Pair-level precision/recall can therefore miss whether a recall group has at least one correct Amazon product near the top of the ranked candidates.

The script reports:

- pair-level precision, recall, F1 and false-positive rate across thresholds from 0.10 through 0.95
- AUROC and AUPRC from the existing OOF probabilities
- Top-1, Top-3, Top-5 and Top-10 hit rates within recall groups that contain at least one reviewed MATCH

## Research integrity

The review labels currently form a development adjudication set, not an independently annotated gold-standard test set. Threshold selection and ranking analysis here are therefore exploratory model-development evidence.

Group ranking metrics are computed **only within the reviewed candidates**. They must not be presented as retrieval performance over the full 84,037-candidate population.

The eventual publication-quality evaluation should use an independently adjudicated holdout set with recall-group separation and a chronological protocol where appropriate.
