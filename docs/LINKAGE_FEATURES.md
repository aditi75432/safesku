# Linkage pairwise features

Candidate generation identifies plausible CPSC ↔ SaferProducts pairs.
Feature extraction represents each pair using transparent identity signals.

Current features include:

- exact UPC
- CPSC UPC count and incident UPC presence
- shared product-token count
- product-token Jaccard
- CPSC product-name coverage
- incident identity-text coverage
- product-name substring indicator
- character sequence similarity
- presence of incident brand/model/manufacturer/retailer
- whether incident brand/model/manufacturer text occurs in the CPSC
  product name

No feature value is itself an entity-resolution decision.

## Labels

The feature-review artifact marks:

```text
positive_seed
unlabeled
```

Exact UPC pairs are strong identity seeds. Non-UPC candidates are intentionally
left unlabeled. They must not be converted to automatic negatives because
candidate generation did not establish that they are different products.

Run:

```powershell
python scripts\\build_linkage_feature_review.py
```

Outputs:

```text
data/benchmark/linkage/feature_review.jsonl
data/benchmark/linkage/feature_review_manifest.json
```

The next stage will create a human-reviewed MATCH/NON_MATCH/UNCERTAIN label
set from a stratified sample of these candidates.
