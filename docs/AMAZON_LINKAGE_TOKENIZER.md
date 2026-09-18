# Amazon linkage tokenizer test fix

The failing test was exposing a real design issue rather than requiring a test-only workaround.

Product identity data often contains short numeric or alphanumeric tokens such as:

- `12`
- `1000`
- `5T`
- `X1`

The tokenizer therefore keeps tokens of length >= 2 and removes ordinary stopwords. This preserves useful product-identity evidence while still avoiding one-character noise.

The test now verifies that behavior directly.
