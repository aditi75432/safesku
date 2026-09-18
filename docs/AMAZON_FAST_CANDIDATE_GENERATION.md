# SafeSKU Fast Amazon Candidate Generation

## Why the old run became slow

The Amazon metadata corpus grew to about 5.06M products. The previous candidate generator built a global token -> ASIN index for the entire corpus and kept large posting sets in memory.

SafeSKU has only 1,005 CPSC product queries. We can exploit that.

## New approach

The index builder first reads the small CPSC benchmark and collects the tokens that actually occur in CPSC product names. It then scans the Amazon metadata once.

For each Amazon title it:

1. tokenizes the title;
2. considers only tokens that occur in CPSC product names;
3. keeps at most 251 postings per token;
4. retains only tokens whose final Amazon document frequency is <= 250;
5. retains product metadata only for ASINs appearing in those rare postings or matching a CPSC UPC.

This avoids keeping a 5M-product global posting index in memory.

The candidate generator then operates on this compact index and does not rescan the Amazon corpus.

## Commands

Build the index once:

```powershell
python scripts\build_amazon_cpsc_index.py
```

Generate candidates:

```powershell
python scripts\build_cpsc_amazon_candidates.py
```

Profile:

```powershell
python scripts\profile_cpsc_amazon_coverage.py
```

The first command still scans the 5M-product file once. Progress is printed every 250,000 rows.

After the index exists, candidate generation should be fast because it only walks postings relevant to the 1,005 CPSC queries.

The index is local experiment state and must not be committed.
