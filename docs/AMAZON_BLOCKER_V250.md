# SafeSKU Amazon Blocker v250

The blocking sensitivity experiment showed the following operating points on the current 312,028-product Amazon slice:

- DF <= 50: 343 recalls, 2,129 candidates
- DF <= 100: 482 recalls, 5,068 candidates
- DF <= 250: 615 recalls, 14,433 candidates
- DF <= 500: 691 recalls, 30,325 candidates

The `DF <= 250` setting is the current operating point because it retains materially more recall coverage than 100 while keeping the candidate population much smaller than 500 and removing the very large generic buckets observed at the original unrestricted lexical blocker.

This is a candidate-generation decision, not a claim that 250 is universally optimal. The threshold should be revisited after we add the remaining Amazon metadata categories and after a labeled CPSC->Amazon review subset exists.

## Production blocker

A candidate is retained when:

`exact UPC`

OR

`at least 2 shared CPSC product-name tokens AND at least 1 shared token appears in <= 250 Amazon product titles`.

Brand is not used as a blocking key.

## Command

```powershell
python scripts\build_cpsc_amazon_candidates.py
```

The command accepts overrides:

```powershell
python scripts\build_cpsc_amazon_candidates.py --max-token-document-frequency 100
```

The persisted candidate artifact is complete and records the blocker parameters in its manifest.
