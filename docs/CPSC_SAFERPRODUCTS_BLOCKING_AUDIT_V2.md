# CPSC ↔ SaferProducts blocking audit v2

The first blocking audit showed that broad identity-token blocking was too
large. It also used an unreliable CPSC brand proxy, so `brand=0` could not be
interpreted as evidence that CPSC brands were unavailable.

This v2 audit removes that misleading brand conclusion and evaluates blocking
signals that are directly grounded in the fields we actually have:

- exact UPC
- exact CPSC product-name phrase contained in incident identity text
- at least 2 product-name tokens shared with an incident
- at least 3 product-name tokens shared with an incident
- CPSC manufacturer/importer/distributor name matched to SaferProducts
  manufacturer
- union of the independent channels

It also measures recovery of the 13 exact-UPC identity seeds without using UPC.
Those seed pairs are high-confidence identity examples, not complete ground
truth.

Run:

```powershell
python scripts\analyze_cpsc_saferproducts_blocking_v2.py
```

Output:

```text
data/benchmark/linkage/blocking_audit_v2.json
```
