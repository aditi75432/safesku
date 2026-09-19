# SafeSKU User Guide

SafeSKU is an evidence-grounded marketplace product-safety investigation workspace. The normal user experience is:

```text
Upload one bundle
      ↓
SafeSKU validates the data
      ↓
SafeSKU ingests and indexes the workspace
      ↓
Search recalls/products
      ↓
Run an investigation
      ↓
Review ambiguous marketplace identity
      ↓
Export an auditable safety case
```

## 1. Start with the Data Workspace

Open the **Data workspace** tab. Choose **Add a SafeSKU data bundle**.

The preferred file is a `.zip` bundle that follows `docs/BUNDLE_FORMAT.md`.

You do not need to upload five separate files. SafeSKU reads the manifest and discovers the available sources for you.

## 2. What a bundle should contain

Recommended minimum for marketplace investigation:

```text
CPSC recalls
SaferProducts.gov incidents
Amazon product metadata
```

Optional:

```text
Amazon reviews
SafeSKU linkage candidates
```

A complete example bundle can therefore look like:

```text
safesku-bundle.zip
├── manifest.json
└── datasets/
    ├── cpsc/recalls.jsonl
    ├── saferproducts/incidents.jsonl
    ├── amazon_products/product_metadata.jsonl
    ├── amazon_reviews/reviews.jsonl
    └── linkage/candidates.jsonl
```

## 3. After upload

Wait until the datasets show **READY**.

The workspace reports:

```text
records received
records accepted
records rejected
source type
fingerprint
```

Rejected records are not silently discarded. The dataset status records the rejection count and the application reports ingestion failures.

## 4. Analyze the workspace

In local developer mode, click **Analyze all**.

In AWS cloud mode, the analysis workflow starts automatically after the upload is accepted. You can watch the job in the workspace until it becomes **COMPLETED**.

## 5. Investigate a recall

Open the **Investigator** tab.

Search using:

```text
22754
```

or a distinctive product term.

Select a recall and click **Investigate**.

SafeSKU builds a safety case from source evidence. The current investigation tools include:

```text
search_cpsc_recall
find_amazon_candidates
get_saferproducts_incidents
build_safety_timeline
verify_evidence
```

The agent may orchestrate these tools in AWS Bedrock/Strands, but the source records remain authoritative.

## 6. Read marketplace identity carefully

A candidate is not automatically the same product merely because its title looks similar.

SafeSKU exposes identity evidence such as:

```text
UPC agreement
brand agreement
model agreement
category agreement
token overlap
title similarity
blocking source
```

Ambiguous candidates should remain **NEEDS REVIEW**.

Use:

```text
CONFIRM / MATCH
REJECT / NON_MATCH
DEFER / UNCERTAIN
```

The decision becomes part of the investigation record.

## 7. Read the timeline

SafeSKU separates event time from model time.

For each incident it can show:

```text
incident date
publication date
official recall date
marketplace evidence date
```

For a pre-recall public signal, the product calculates lead time as the interval between the earliest eligible public evidence and the official recall date.

This is a temporal association. It should not be read as proof of causality.

## 8. Open evidence

Every evidence item has a stable SafeSKU evidence identifier. Click the item to inspect its structured source record.

The expected workflow is:

```text
finding
  ↓
evidence ID
  ↓
source record
  ↓
reviewer decision
```

## 9. Review queue

The review queue is for cases where automatic identity resolution is not sufficient.

A good reviewer decision should answer:

> Are these two records the same underlying product entity?

It should not answer a broader question such as whether the product is legally unsafe. SafeSKU is an investigation aid, not a legal determination engine.

## 10. Export

Use **Export JSON** when you want the machine-readable investigation record.

Use **Export CSV** for a compact analyst-oriented report.

The exported case includes the recall, evidence, marketplace candidates and recorded review decisions.

## 11. Historical demo cases

SafeSKU may ship with a small historical dataset for demonstration. Those cases are replayable examples, not the product's source of truth.

The main product flow is always:

```text
user data
   ↓
workspace
   ↓
investigation
```

## 12. Troubleshooting

### Search returns no matches

Check that a CPSC dataset is **READY** and that the recall was imported. In AWS, also check that the current workspace snapshot exists.

### Bundle upload fails

Open the bundle locally and verify `manifest.json`, member paths, SHA-256 values and byte counts.

### Amazon candidate list is empty

Make sure Amazon product metadata and, if applicable, the SafeSKU linkage artifact are present. A recall can still be investigated without an Amazon match, but the marketplace identity section will be limited.

### Review evidence is empty

The current benchmark includes product metadata. Review text only appears for ASINs that have actually been ingested as `amazon_reviews` records.

## 13. Operator principle

SafeSKU follows one rule throughout the product:

**Evidence first. AI second. Human decisions stay explicit.**
