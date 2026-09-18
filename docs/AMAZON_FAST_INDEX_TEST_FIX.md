# Amazon fast-index test fix

The first fast-index patch intentionally changed the candidate generator API:

- `build_amazon_cpsc_index.py` owns index construction.
- `build_cpsc_amazon_candidates.py` consumes that index.

One older test still imported the removed `build_indices()` helper from the previous full-corpus candidate implementation. This caused pytest collection to fail before any test executed.

The fix updates the test to the new public API. No production behavior is changed by this fix.
