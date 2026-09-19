# SafeSKU Bundle Format

SafeSKU uses one portable ZIP file as the normal onboarding artifact. The bundle is a transport format. It does not replace the source systems and it does not make an AI-generated statement authoritative.

## 1. ZIP layout

```text
safesku-bundle.zip
├── manifest.json
└── datasets/
    ├── cpsc/
    │   └── recalls.jsonl
    ├── saferproducts/
    │   └── incidents.jsonl
    ├── amazon_products/
    │   └── product_metadata.jsonl
    ├── amazon_reviews/
    │   └── reviews.jsonl
    └── linkage/
        └── candidates.jsonl
```

Only the dataset types that are available need to be present. For the strongest marketplace investigation, provide CPSC, SaferProducts and Amazon product metadata. Amazon reviews are optional and should only be included when they are genuine review-level records.

## 2. manifest.json

The root manifest must use this contract:

```json
{
  "format": "safesku.bundle.v1",
  "bundle_id": "BND-EXAMPLE",
  "created_at": "2026-09-19T00:00:00+00:00",
  "workspace": {
    "name": "My safety workspace",
    "description": "Marketplace safety investigation data"
  },
  "datasets": [
    {
      "source_type": "cpsc",
      "path": "datasets/cpsc/recalls.jsonl",
      "name": "recalls.jsonl",
      "description": "Official CPSC recall records",
      "sha256": "<64 hex characters>",
      "bytes": 12345
    }
  ]
}
```

`sha256` must be the SHA-256 of the exact ZIP member bytes. `bytes` must be the exact uncompressed member size. SafeSKU verifies both values before ingesting a member.

## 3. Supported source types

### CPSC recalls

Required practical fields:

```text
recall_number
recall_date
product_name
```

Useful fields:

```text
title
description
hazards
brand
model
upc
category
url
source_record_id
```

### SaferProducts.gov incidents

Required practical fields:

```text
source_record_id
incident_date
publication_date
product_description
incident_description
```

Useful fields:

```text
product_brand
product_model
product_upc
manufacturer_name
retailer_name
recall_number
```

### Amazon product metadata

Required:

```text
parent_asin  (or asin)
title
```

Useful:

```text
brand
model
upc
manufacturer
main_category
```

### Amazon reviews

Required:

```text
asin or parent_asin
review text
```

Recommended:

```text
review_id
rating
timestamp / review_date
title
verified_purchase
```

### SafeSKU linkage

Required:

```text
cpsc_recall_number / recall_number
amazon_parent_asin / parent_asin
```

Useful evidence fields include the blocking source, UPC agreement, token overlap, title similarity, brand relation, model information and any reviewed label.

## 4. What users should upload

For a normal SafeSKU workspace, the preferred input is **one ZIP bundle**. Users should not have to understand SafeSKU's internal research directory.

For this hackathon deployment, the browser upload path is intended for bundles up to 500 MiB. Larger enterprise feeds should use a direct S3 ingestion path rather than sending data through API Gateway.

Do not place a 15 GB full marketplace catalog into the judge bundle merely to reproduce the benchmark. For demos, create a focused bundle containing the product records represented in the linkage candidate graph. For a production integration, keep the full marketplace feed in S3 and run the larger ingestion pipeline there.

## 5. Bundle safety rules

SafeSKU rejects:

- missing `manifest.json`
- unsupported source types
- missing members declared by the manifest
- ZIP path traversal
- checksum mismatches
- byte-count mismatches
- empty datasets
- records that do not satisfy the minimum source contract

The source records remain the evidence. SafeSKU stores provenance and derived relationships so investigators can trace a finding back to a source record.
