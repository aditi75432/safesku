# SafeSKU Amazon Reviews'23 Metadata

SafeSKU uses the **Amazon Reviews'23** dataset from McAuley Lab as the marketplace source.

Official source:

https://amazon-reviews-2023.github.io/main.html

The dataset provides item metadata including title, descriptions, features, details, brand-like fields, and `parent_asin`. Reviews provide `rating`, `title`, `text`, `timestamp`, `verified_purchase`, `helpful_vote`, `asin`, and `parent_asin`.

## Why metadata first

We do not download the entire review corpus. The 2023 release contains 571.54M reviews, so pulling everything would be unnecessary for this project.

We first download category-level metadata and determine which Amazon products can be linked to our CPSC recall population. Only then will we download review data for categories/products that actually contribute to the experiment.

## Commands

Start with the two smaller default categories:

```powershell
python scripts\download_amazon_metadata.py
```

This downloads:

- `Appliances`
- `Baby_Products`

To add a category:

```powershell
python scripts\download_amazon_metadata.py --category Toys_and_Games
```

To download all configured categories, use:

```powershell
python scripts\download_amazon_metadata.py --all-configured
```

Do this only after checking available disk space. Several configured metadata categories are hundreds of MB to multiple GB.

Normalize:

```powershell
python scripts\normalize_amazon_metadata.py
```

Profile:

```powershell
python scripts\profile_amazon_metadata.py
```

## Reproducibility

The raw files stay outside Git. The downloader writes SHA-256 hashes to:

`data/amazon/raw/metadata/download_manifest.json`

The normalized artifact is generated locally and is also excluded from Git by the SafeSKU data ignore rules.

## Identity fields

Amazon metadata uses `parent_asin` as the stable parent product identifier. Amazon's documentation notes that different colors/styles/sizes can share the same parent ID, so downstream product-level joins should deliberately decide whether the unit of analysis is the parent product or the individual ASIN.
