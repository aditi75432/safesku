# SafeSKU Entity-Resolution Modeling

## What this stage does

This stage turns the 150-row adjudicated linkage sample into a controlled model-development/evaluation experiment.

Rows labeled `UNCERTAIN` are excluded from supervised training and evaluation. The remaining rows are split with `StratifiedGroupKFold`, using the CPSC recall number as the group. This prevents candidate rows from the same recall from being split across train and test folds.

## Models

We compare simple baselines before using a learned matcher:

1. `upc_only`: exact UPC is a match.
2. `token_and_similarity`: exact UPC OR at least 3 shared product-name tokens with Jaccard >= 0.20.
3. `logistic_lexical`: logistic regression using lexical similarity features.
4. `logistic_all`: logistic regression using lexical + identifier/context features.
5. `hist_gradient_boosting`: nonlinear classifier using the full structured feature set.

The learned models use class balancing because the development labels are not perfectly balanced.

## Features

The full matcher uses:

- exact UPC
- shared product-token count
- product-token Jaccard
- product-name sequence similarity
- CPSC-name token coverage
- incident-name token coverage
- incident brand in CPSC name
- incident model in CPSC name
- manufacturer in CPSC name

We intentionally exclude recall IDs, incident IDs, URLs, raw dates, temporal status, selection reasons, annotation metadata, and reviewer notes.

## Why grouped cross-validation

A random row split is unsafe here because multiple candidates can belong to the same recall. Grouped splitting keeps all candidates for a given recall in one fold.

This is a development benchmark, not the final paper gold-standard benchmark. The labels are senior working adjudications.

## Outputs

Running the script produces:

- `model_metrics.json`: overall and per-fold metrics
- `model_comparison.csv`: compact model comparison
- `oof_predictions.csv`: out-of-fold predictions for every labeled row

Metrics include precision, recall, F1, false-positive rate, ROC-AUC, and average precision where defined.

## Next

Use the results to select a linkage model for downstream evidence-graph construction. Do not train on `UNCERTAIN`. Do not use downstream temporal/recalldata fields as linkage features.
