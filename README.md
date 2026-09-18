# SafeSKU linkage human-review patch

Adds a deterministic stratified human-review benchmark builder for the existing
`data/benchmark/linkage/feature_review.jsonl` artifact.

The script deliberately keeps entity-resolution labels separate from temporal
eligibility and never creates automatic negative labels.
