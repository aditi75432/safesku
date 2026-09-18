# SafeSKU Amazon Blocking Diagnostic

The latest CPSC -> Amazon run produced:

- 435 recalls with candidates
- 36,798 candidate pairs
- median 8 candidates
- p90 179
- maximum 6,354

Before adding more Amazon categories or review data, we need to understand whether the lexical blocker is too broad.

## Two diagnostics

### 1. UPC overlap

`audit_cpsc_amazon_identity_overlap.py` measures the intersection of normalized CPSC and Amazon UPC values directly.

A zero intersection means the two currently loaded metadata populations share no normalized UPC values. That is a data characteristic to investigate, not something to fix by inventing matches.

### 2. Rarity-threshold sensitivity

`audit_cpsc_amazon_blocking_sensitivity.py` measures a stricter lexical policy:

`at least 2 shared CPSC product-name tokens AND at least 1 shared token has Amazon document frequency <= threshold`

This is evaluated for several thresholds without changing production code.

The goal is to find a threshold that materially reduces generic buckets while retaining useful recall coverage.

## Commands

```powershell
python -m pytest apps\api\tests -q
python scripts\audit_cpsc_amazon_identity_overlap.py
python scripts\audit_cpsc_amazon_blocking_sensitivity.py
```

Do **not** change the production blocker from these diagnostics yet. Choose the new threshold only after inspecting the sensitivity table.

## Why rarity matters

A shared token like `baby`, `coffee`, or `air` appears in many unrelated marketplace products. A shared term like a specific product family, model fragment, or unusual brand/product phrase is more discriminative.

The production matcher will still use brand/model/description features after blocking. Rarity is only a candidate-generation control.

## Next decision

Use the sensitivity table to choose the blocker threshold, rerun candidate generation, then sample candidate quality before downloading Amazon reviews.
