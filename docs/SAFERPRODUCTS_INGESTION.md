# Resumable SaferProducts ingestion

The live SaferProducts.gov service has been observed to cap a `$top=100`
request at 50 records.

SafeSKU therefore:

1. Advances `$skip` by the number of records actually returned.
2. Writes every raw page immediately.
3. Reuses complete monthly raw windows on `--resume`.
4. Continues incomplete monthly windows from the number of records already
   stored.
5. Writes one normalized JSONL file per completed month.
6. Writes `manifest.partial.json` after every completed month.
7. Writes the final `manifest.json` only after the complete requested period
   finishes.

## Resume command

```powershell
python scripts\ingest_saferproducts.py --start-date 2020-01-01 --end-date 2023-09-30 --page-size 100 --resume
```

A KeyboardInterrupt leaves downloaded raw pages intact. Re-running with
`--resume` reconstructs completed windows locally and continues incomplete
windows without starting the whole acquisition again.
