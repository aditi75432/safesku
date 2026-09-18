# SafeSKU Historical Benchmark Protocol

## Purpose

The historical benchmark is separate from the live/demo CPSC dataset. Its purpose is to support leakage-safe experiments that combine historical CPSC recalls with Amazon Reviews'23 data.

## CPSC benchmark window

The initial benchmark window is configurable. The intended first run is 2020-01-01 through 2023-09-30 so it overlaps the time coverage of Amazon Reviews'23.

The CPSC API is queried in fixed calendar windows rather than one very large request. Every raw response is retained under `data/raw/cpsc_benchmark/`.

## Record identity

`source_record_id` is the deduplication key. `recall_number` is not used as a unique key because more than one source record can share a recall number.

## No category pre-filtering at ingestion

The historical CPSC benchmark initially keeps all recall API records in the date window. Category/product-family filtering happens later, after the Amazon overlap analysis, so the selection rule remains auditable.

## Leakage rule

For downstream experiments, only evidence with a timestamp strictly earlier than the recall event may contribute to a pre-recall safety signal. Evidence published after the recall date must not be used for lead-time calculations.

## Benchmark layers

1. **Raw CPSC snapshots**: immutable API responses by date window.
2. **Normalized CPSC recalls**: validated `RecallRecord` objects in `data/benchmark/cpsc/recalls.jsonl`.
3. **Later selection layer**: product families and recall cases with sufficient Amazon overlap.
4. **Evaluation layer**: recalled products plus matched non-recalled controls, with chronological train/validation/test splits defined before model fitting.

## Reproducibility

`manifest.json` records the requested date range, chunk size, counts, raw snapshot hashes, processed-file hash, and the deduplication/selection rules used to create the benchmark.
