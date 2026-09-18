# SafeSKU CPSC -> Amazon Candidate Audit Fix

## Why this patch exists

The first CPSC -> Amazon run produced:

- 435 of 1,005 recalls with candidates
- 36,798 candidate pairs
- 0 exact UPC candidates
- 35,444 rows written to the review artifact

Two issues needed correction before using these candidates for research:

### 1. Brand was accidentally used as a blocking key

The earlier implementation added every Amazon product with a matching brand to the lexical candidate set. That conflicts with the intended blocking policy of:

`exact UPC OR at least two shared CPSC product-name tokens`

Brand is useful as a downstream linkage feature, but not as a standalone blocking key.

### 2. Candidate output was truncated

The old default wrote at most 5,000 candidates per product. Therefore the manifest's 36,798 complete count differed from the 35,444 rows actually available in the candidate file.

The new default writes the complete candidate set. An optional `--review-limit` is available only when a bounded inspection artifact is intentionally desired.

## Research consequence

The next coverage numbers must be generated from the corrected, complete candidate artifact.

A zero exact-UPC overlap is not automatically a bug. The current Amazon slice has limited UPC coverage, and the CPSC benchmark has only a subset of recalls with UPCs. We should diagnose the actual normalized identifier overlap before deciding whether the zero count is meaningful.

## Commands

```powershell
python -m pytest apps\api\tests -q
python scripts\build_cpsc_amazon_candidates.py
python scripts\profile_cpsc_amazon_coverage.py
```

Only after these corrected numbers are known should we decide whether to download more Amazon categories or review-level data.
