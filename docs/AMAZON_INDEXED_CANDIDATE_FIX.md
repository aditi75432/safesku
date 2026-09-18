# Amazon indexed-candidate fix

The first bounded-index candidate generator was too restrictive.

The intended blocker is:

`at least two shared product-name tokens AND at least one shared token is rare (Amazon DF <= 250)`.

The index only needs to retain postings for **rare** tokens. Once a rare token identifies a bounded set of Amazon products, the generator must inspect each candidate's full title and count **all** shared CPSC tokens. The second shared token may be common.

The previous implementation incorrectly counted only rare-token postings, which turned the rule into:

`at least two shared rare tokens`.

That is stricter and explains why the indexed run dropped to only 50 recalls.

This patch restores the intended policy while keeping the fast bounded-index architecture.
