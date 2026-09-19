# SafeSKU Judge Bundle

The repository contains a 15 GB normalized Amazon catalog. Do **not** ZIP that file for a browser upload.

The portable judge bundle instead contains:

- the full historical CPSC recall benchmark;
- the full historical SaferProducts incident benchmark;
- the SafeSKU Amazon linkage candidate artifact;
- only the Amazon products referenced by those real candidates.

This keeps the demo bundle self-contained while avoiding a 15 GB browser upload. The full catalog remains a server-side benchmark artifact and is used for the large-scale linkage experiments.

## Build

From the repository root:

```powershell
python scripts\build_safesku_judge_bundle.py
```

The script streams the 15 GB Amazon JSONL once, extracts only candidate ASINs, then creates:

```text
data\runtime\judge_bundle\amazon_products_for_candidates.jsonl
data\bundles\safesku-judge-bundle.zip
```

Typical flow:

```text
15 GB Amazon catalog
        |
        |  stream + ASIN filter
        v
candidate-linked Amazon products
        |
        +---- CPSC recalls
        +---- SaferProducts incidents
        +---- linkage candidates
        v
portable SafeSKU judge bundle
```

## Why this split exists

A browser-facing upload should be practical. A full 8.67M-product corpus belongs in server-side object storage/search infrastructure, not in a ZIP a judge has to upload manually.
