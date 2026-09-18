# SafeSKU human-review test fix

The human-review script had an overly strict hard-coded validation:

    sample_size >= 13

That is only true for the current production dataset, where there are 13 exact-UPC seeds. Unit tests intentionally use smaller synthetic seed sets. The existing validation immediately after seed discovery already checks the actual number of seeds, so the hard-coded check is removed and replaced with a generic positive-sample-size check.

No change to the sampling policy or production output is required.

## Apply

Extract this patch at the repository root and overwrite the existing files when prompted.

Then run:

    python -m pytest apps\api\tests -q

The expected result is 48 passed, 3 warnings (assuming no unrelated changes).
