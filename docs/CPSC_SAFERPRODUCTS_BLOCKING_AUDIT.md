# CPSC ↔ SaferProducts candidate-blocking audit

The previous broad token candidate search produced 368–6,496 candidates per
CPSC recall. That is too broad to use directly for entity resolution.

This audit compares narrower, auditable blocking strategies:

- exact UPC
- normalized brand
- exact brand + model when both are available
- any identity token
- rarest CPSC identity token
- intersection of the two rarest identity tokens

The audit measures candidate-set size only. It does not declare candidates to
be true matches.

The goal is to select a blocking strategy that reduces the search space before
a future pair scorer is introduced.
