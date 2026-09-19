# SafeSKU Amazon Product-Linkage Review Set

This stage creates a controlled review sample from the current CPSC -> Amazon candidate population.

The target of review is **product identity**, not safety classification.

## Sampling

The default sample size is 200. All exact-UPC candidates are retained. The remaining rows are stratified across:

- lexical similarity;
- Amazon model availability;
- brand relation;
- candidate bucket size.

This keeps the review set useful for finding both obvious matches and hard cases.

## Labels

- `MATCH`: same underlying product entity/SKU.
- `NON_MATCH`: different product/entity.
- `UNCERTAIN`: evidence is insufficient or contradictory.

## Commands

```powershell
python scripts\build_amazon_review_set.py
```

Output:

`data/benchmark/amazon_linkage/amazon_human_review_set.csv`

The CSV has two intentionally empty columns:

- `review_label`
- `reviewer_notes`

These are reserved for the SafeSKU adjudication pass.

Do not treat blocking candidates as positives. Candidate generation only establishes that a pair is worth considering.
