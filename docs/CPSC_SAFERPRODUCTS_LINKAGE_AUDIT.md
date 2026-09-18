# CPSC ↔ SaferProducts linkage audit

Before implementing an automatic entity resolver, SafeSKU measures the
identity-field coverage and candidate-search behavior of the real benchmark.

The audit deliberately does **not** declare any fuzzy candidate a true match.

It measures:

- CPSC product-name and description coverage
- CPSC UPC coverage
- SaferProducts brand/model/description/UPC/manufacturer/retailer coverage
- exact UPC intersections
- broad token-overlap candidate counts

This tells us whether deterministic identifiers are sufficient and how
aggressive candidate generation should be before adding a learned/semantic
matcher.

Run:

```powershell
python scripts\analyze_cpsc_saferproducts_linkage.py
```

Output is written to:

```text
data/benchmark/linkage/linkage_audit.json
```

The generated audit data stays out of Git.
