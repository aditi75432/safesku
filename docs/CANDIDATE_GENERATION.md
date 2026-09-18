# CPSC ↔ SaferProducts candidate generation

The blocking audit on the real benchmark found:

- exact UPC: sparse but high-confidence;
- broad identity-token overlap: too large;
- >=2 CPSC product-name tokens: much smaller and recovered 11/13 exact-UPC
  seed pairs.

SafeSKU therefore uses a candidate-generation union:

```text
exact UPC
OR
at least 2 shared tokens from the CPSC product name
```

This is a blocking policy, **not** an entity-match decision.

Every exact-UPC candidate is retained.

For a human review artifact, up to `--top-k` additional non-UPC candidates
are retained per recall, ranked transparently by:

1. exact UPC flag
2. number of shared product-name tokens
3. product-token Jaccard similarity
4. stable incident ID

The complete candidate set remains available through
`generate_candidates()` and is not truncated by the review export.

Run:

```powershell
python scripts\generate_cpsc_saferproducts_candidates.py --top-k 5
```

Outputs:

```text
data/benchmark/linkage/candidate_review.jsonl
data/benchmark/linkage/candidate_generation_manifest.json
```

Neither output is a ground-truth label set. They are diagnostic/review
artifacts for the next pair-scoring and labeling stage.
