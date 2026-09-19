# SafeSKU Amazon Linkage Modeling Benchmark

## Purpose

This benchmark moves from the Amazon candidate generator to a learned product-identity resolver. It answers a narrower question:

> Given a CPSC recall and an Amazon candidate produced by the locked category-aware blocker, how well can pair-level evidence distinguish the same product from a non-match?

The current 200-row Amazon review sample contains 31 `MATCH`, 151 `NON_MATCH`, and 18 `UNCERTAIN` development labels. The 18 `UNCERTAIN` rows are excluded from supervised training and evaluation.

## Integrity controls

The current labels are **working adjudication**, not an independently annotated gold-standard dataset. They are appropriate for model development and debugging, but paper-level claims should later use an independently reviewed audit set.

Evaluation uses `StratifiedGroupKFold` with the CPSC recall number as the group. Thus candidates belonging to the same recall do not appear in both train and test folds.

Reviewer notes, adjudication confidence, adjudicator identity, labeling-basis fields, dates, recall IDs, ASIN IDs, and selection metadata are excluded from model features.

## Models and baselines

- `upc_only`: exact UPC only.
- `token_similarity`: transparent lexical rule using shared product tokens and token Jaccard, plus exact UPC.
- `strict_title`: lexical blocker strengthened with whole-title similarity.
- `logistic_lexical`: regularized logistic regression using lexical features.
- `logistic_all`: logistic regression using lexical + soft brand/model/manufacturer signals.
- `hist_gradient_boosting`: non-linear model using the same all-feature set.

## Features

The learned models use:

- exact UPC
- shared product-name token count
- product-name token Jaccard
- whole-name/title sequence similarity
- Amazon-title token coverage
- CPSC-name coverage inside Amazon title
- Amazon brand present in CPSC name
- brand-token overlap with Amazon title
- exact Amazon model phrase in title
- manufacturer phrase in title

These are pair features, not target-derived metadata.

## Why this stage matters

The blocker is intentionally conservative enough to control search cost, but candidate generation alone cannot establish identity. This benchmark measures whether a separate resolver can re-rank or filter those candidates using richer evidence.

The next stage after this benchmark is **not** to claim production-quality linkage immediately. First inspect grouped out-of-fold precision/recall and error cases; then lock a decision policy and run it against the full 84,037-candidate population.
