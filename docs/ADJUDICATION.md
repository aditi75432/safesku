# SafeSKU: 150-Row Linkage Adjudication

## Decision labels

- **MATCH**: the CPSC and SaferProducts records refer to the same underlying product entity/SKU.
- **NON_MATCH**: the records refer to different products/entities.
- **UNCERTAIN**: the evidence overlaps but does not establish the exact recalled variant, model, or identifier.

## Evidence order

The adjudication prioritizes exact identifiers and recall scope:

1. Exact UPC.
2. Exact/compatible model within the CPSC recall scope.
3. Brand + product description + specific product-family evidence.
4. Lexical similarity is supporting evidence only.

## Temporal separation

Whether an incident was publicly available before the recall is evaluated independently from product identity.

## Research integrity

This is a senior working adjudication of the 150-row sample. It is **not independent human gold-standard annotation**. The labels are appropriate for development and bootstrapping. A paper should disclose the annotation process and should not claim inter-annotator agreement unless independent annotations are later collected.

## Next

Use MATCH/NON_MATCH rows for development of the entity-resolution model, exclude UNCERTAIN rows from supervised training, and split by recall/product group rather than randomly by row to avoid leakage.
