
# Linkage feature test fix

`token_jaccard()` intentionally rounds feature values to six decimal places.
The test therefore uses a bounded floating-point comparison instead of
requiring the rounded representation to equal the unrounded Python fraction
exactly.
