# SafeSKU Amazon Linkage Audit

The current CPSC -> Amazon run produced 435 recalls with candidates and 36,798 candidate pairs, with a maximum candidate bucket of 6,354.

Before downloading more Amazon categories or any review shards, we audit two things:

1. **Identifier overlap**: whether normalized CPSC UPCs actually intersect Amazon UPCs.
2. **Blocking behavior**: which recalls are generating very large candidate buckets.

This prevents us from expanding the Amazon corpus before knowing whether the current blocker is sufficiently selective.

## Commands

```powershell
python -m pytest apps\api\tests -q
python scripts\audit_cpsc_amazon_identity_overlap.py
python scripts\audit_cpsc_amazon_blocking.py
```

Outputs:

- `data/benchmark/amazon_linkage/identity_overlap_report.json`
- `data/benchmark/amazon_linkage/blocking_audit_report.json`

Do not change the blocker again until these reports have been inspected.

## Decision rule

- If UPC intersection is zero, diagnose the CPSC/Amazon normalization and source-field overlap before concluding UPC matching is unavailable.
- If a small number of recalls create thousands of candidates, tighten the lexical blocker before adding categories.
- Only when candidate volumes are controlled should additional Amazon categories and review data be added.
