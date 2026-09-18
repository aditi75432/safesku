# Amazon fast-index clean fix

Two issues were corrected together:

1. `build_cpsc_amazon_candidates.py` contained an accidental plain-text footer, which caused a `SyntaxError`.
2. The older `test_cpsc_amazon_candidates.py` still imported the removed `build_indices()` helper from the previous implementation.

The production API is now:

- `build_amazon_cpsc_index.py` -> `build_index(cpsc_path, amazon_path)`
- `build_cpsc_amazon_candidates.py` -> `generate_candidates(product, recall, index)`

Both test modules now use that API.
