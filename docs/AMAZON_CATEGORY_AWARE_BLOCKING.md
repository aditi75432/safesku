# SafeSKU Category-Aware Amazon Blocking

The Amazon catalog expanded from 5.06M to 8.67M products. With global token document frequency, that expansion reduced CPSC coverage because tokens that were rare before became globally common.

Current policy:

`exact UPC`

OR

`at least 2 shared CPSC product-name tokens AND at least 1 shared token is rare within an Amazon source category (DF <= 250)`.

Candidate discovery uses category-local rare-token postings. After discovery, the complete Amazon title is inspected so the second shared token may be common.

The current CPSC benchmark has incomplete product category fields, so the blocker does not require a CPSC category.

The existing index must be rebuilt because its rarity scope changed from global to category-local.

Commands:

```powershell
python -m pytest apps\api\tests -q
python scripts\build_amazon_cpsc_index.py
python scripts\build_cpsc_amazon_candidates.py
python scripts\profile_cpsc_amazon_coverage.py
```

This is candidate generation, not final entity resolution. Do not download Amazon reviews until candidate coverage and product identity quality are measured.
