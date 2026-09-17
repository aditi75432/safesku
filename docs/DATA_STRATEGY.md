# Data Strategy

## Sources

### CPSC Recalls

Use the official CPSC Recall REST API as the authoritative recall source.

Required fields for the canonical recall record:

- recall_number
- recall_date
- company
- product_type
- product_description
- hazard
- manufactured_in
- upc
- source_url

### SaferProducts.gov

Use public incident reports where API access is available.

Required fields:

- report_number
- incident_date
- publication_date
- manufacturer
- product_brand
- product_model
- product_description
- incident_description
- retailer
- source_url

### Amazon Reviews 2023

Use a research subset, not the full 571M+ review corpus.

Required review fields:

- parent_asin
- asin
- timestamp
- title
- text
- rating
- helpful_vote
- verified_purchase

Required metadata fields:

- parent_asin
- main_category
- title
- brand
- description
- features
- price
- images

## Temporal rule

For a recall announced on date T:

- training evidence may use records strictly before T;
- the detector must not see the recall record itself;
- it must not use post-T reviews or incident reports;
- the recall announcement is used only as the evaluation endpoint.

This prevents future-information leakage.

## First benchmark unit

One benchmark case represents one recall-linked product family.

For each case we store:

- recall date
- product identity
- pre-recall review window
- pre-recall incident window
- positive evidence
- hard negatives
- first alert timestamp
- lead time

## Data governance

The Amazon Reviews 2023 dataset is made available primarily for research purposes. Treat it as research data and document its provenance and usage conditions in the final project and paper.
