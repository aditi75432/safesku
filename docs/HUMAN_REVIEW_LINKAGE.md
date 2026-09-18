# Human-reviewed CPSC ↔ SaferProducts linkage benchmark

The current `feature_review.jsonl` contains 3,191 candidate pairs, including
13 exact-UPC identity seeds. It is not a ground-truth label set.

This stage creates a deterministic, stratified review set for manual entity
resolution. The default sample has 150 rows and retains all 13 exact-UPC seeds.
The remaining rows are sampled across:

- pre-recall-public pairs
- high lexical similarity
- medium lexical similarity
- candidates with exactly two shared product-name tokens
- lower lexical similarity

A per-recall cap prevents a single recall with many candidates from dominating
the benchmark.

Run:

```powershell
python scripts\build_linkage_review_set.py
```

Outputs:

```text
data/benchmark/linkage/human_review_set.jsonl
data/benchmark/linkage/human_review_set.csv
data/benchmark/linkage/human_review_set_manifest.json
```

## Labeling protocol

Label only **entity identity** in `review_label`:

- `MATCH`: the CPSC recall product and SaferProducts product refer to the same
  underlying product/SKU.
- `NON_MATCH`: they refer to different products/entities.
- `UNCERTAIN`: the available evidence is insufficient or contradictory.

Do not use `pre_recall_public` as a match label. Temporal eligibility and entity
identity are separate dimensions. A pair can be a correct identity match but
still be post-recall and therefore unavailable to a pre-recall detector.

The `initial_label=positive_seed` field means only that the pair has an exact
UPC overlap discovered by the blocking stage. It should not be treated as
proof that every non-UPC row is negative.

The CSV is the manual-review artifact. Keep `review_label` and
`reviewer_notes` as the only fields you edit during labeling.
