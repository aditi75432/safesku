# SafeSKU Bundle Format

Users upload one `.zip` file. The bundle must contain `manifest.json` and one or more datasets under `datasets/`.

## Recommended bundle

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
    │   └── reviews.jsonl              # optional
    └── linkage/
        └── candidates.jsonl           # optional
```

## Required source fields

### CPSC recalls

Recommended fields:

- `source_record_id`
- `recall_number`
- `recall_date`
- `title`
- `product_name`
- `description`
- `hazards`
- `product_upcs`
- `manufacturers`

### SaferProducts incidents

Recommended fields:

- `source_record_id`
- `incident_date`
- `publication_date`
- `incident_description`
- `product_description`
- `product_brand`
- `product_model`
- `product_upc`
- `manufacturer_name`
- `retailer_name`

### Amazon marketplace products

Recommended fields:

- `parent_asin`
- `title`
- `brand`
- `model`
- `upc`
- `manufacturer`
- `categories`

### Amazon reviews

Optional but supported when real review text is available:

- `review_id`
- `asin`
- `parent_asin`
- `review_date`
- `review_title`
- `review_text`
- `rating`
- `verified_purchase`

### SafeSKU linkage candidates

Optional derived artifact:

- `recall_number`
- `parent_asin`
- `title`
- `brand`
- `model`
- `upc`
- `exact_upc`
- `shared_product_token_count`
- `product_token_jaccard`
- `product_name_sequence_similarity`
- `brand_relation`
- `blocking_sources`

## Rules

- UTF-8 encoding.
- JSON Lines means one JSON object per line.
- Stable identifiers are strongly preferred.
- Dates should use ISO `YYYY-MM-DD` or full ISO-8601 timestamps.
- Do not place generated evaluation metrics inside operational source folders.
- Human review labels belong in a dedicated review/evaluation dataset.
- The manifest should declare the source type, member path, byte size, SHA-256, and record count when known.

## Good user experience

A user does not need to know SafeSKU's internal research filenames. The application should accept the bundle, validate it, show exactly which source types were detected, and tell the user what is missing before analysis starts.
