# SafeSKU Results and Validation

## Current workspace scale

The judge bundle has been validated with the following compact real-data slice:

| Source / artifact | Records |
|---|---:|
| CPSC historical recalls | 1,005 |
| SaferProducts.gov historical incidents | 13,696 |
| Amazon marketplace products | 53,632 |
| Supplied SafeSKU linkage candidates | 84,037 |
| OpenSearch identity-candidate documents | 85,537 |
| OpenSearch total documents | 153,870 |

The OpenSearch total is internally consistent with:

```text
1,005 recalls
+ 13,696 incidents
+ 53,632 marketplace products
+ 85,537 identity-candidate records
= 153,870 documents
```

## CPSC ↔ SaferProducts linkage audit

Blocking audit:

| Blocking source | Recalls with candidates | Median | P90 | Max |
|---|---:|---:|---:|---:|
| UPC | 9 | 0 | 0 | 4 |
| Product phrase | 38 | 0 | 0 | 93 |
| Product 2 tokens | 777 | 6 | 47 | 1,510 |
| Product 3 tokens | 397 | 0 | 6 | 448 |
| Company → manufacturer | 3 | 0 | 0 | 3 |
| Union | 783 | 6 | 48 | 1,510 |

Production blocking policy:

```text
exact UPC
OR
at least 2 shared CPSC product-name tokens
```

with strict temporal eligibility:

```text
incident_date < recall_date
AND
publication_date < recall_date
```

## Linkage model benchmark

Historical human review benchmark:

- 140 labeled rows used for modeling
- 10 uncertain rows excluded from the modeling benchmark
- 108 recall groups
- 5 folds
- 73 MATCH
- 67 NON_MATCH

| Model / rule | Precision | Recall | F1 | False-positive rate |
|---|---:|---:|---:|---:|
| UPC only | 1.000 | 0.178 | 0.302 | 0.000 |
| Token + similarity | 0.663 | 0.863 | 0.750 | 0.478 |
| Logistic, all features | 0.768 | 0.726 | 0.746 | 0.239 |
| Logistic, lexical | 0.621 | 0.562 | 0.590 | 0.373 |
| HistGradientBoosting | 0.696 | 0.658 | 0.676 | 0.313 |

These measurements describe the project's historical benchmark slice. They are
not claimed as universal marketplace performance.

## Amazon identity review sample

The selected 200-row Amazon linkage review set contains:

```text
31 MATCH
151 NON_MATCH
18 UNCERTAIN
```

All exact-UPC candidates in the selected sample were adjudicated as MATCH. The
sample is a senior working adjudication set, not an independent gold-standard
ground-truth dataset.

## Engineering validation

Recent local validation gates include:

```text
API tests: 100+ passing before the latest test-isolation fixture
SAM template validation: passing
SAM container build: passing
OpenSearch 3.x compatibility regression: passing
OpenSearch index: 153,870 documents
API search backend: OpenSearch
```

The repository now isolates API tests from the developer's global OpenSearch index
so test results remain deterministic.
