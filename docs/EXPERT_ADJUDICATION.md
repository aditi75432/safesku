# SafeSKU Expert Adjudication

This artifact records a senior-review working pass over the 150-row linkage review sample.

## Decision labels

- MATCH: same underlying product entity/SKU.
- NON_MATCH: different product/entity.
- UNCERTAIN: evidence is insufficient or contradictory.

## Review rule

Identity is judged from source evidence first: UPC, model, brand, product description, recall scope, and incident details. Lexical similarity is supporting evidence only.

Temporal eligibility is a separate dimension. A product can match the recall and still have an incident published after the recall.

## Research integrity

These annotations are a development/bootstrapping layer. They are not independent human gold labels and should not be reported as such in a paper. The included `independent_audit_queue.csv` is the small set to verify independently before using this sample as a formal evaluation benchmark.

## Next experiment

Use non-UNCERTAIN working labels for matcher development only. Keep the independent audit rows untouched by training. After independent labels are available, report precision/recall/F1 and false-match rate on the audited holdout.
