# SaferProducts benchmark audit

The completed historical ingestion reported:

- 45 monthly windows
- 13,696 fetched/reused raw records
- 13,673 unique normalized records
- 23 normalization failures

Before using the corpus for research, run the audit to distinguish:

- normalization failures and their exact reasons,
- duplicate `IncidentReportNumber` values,
- missing incident/publication dates,
- and the final processed JSONL count.

The audit reads the actual raw layout:

```text
data/benchmark/saferproducts/raw/YYYY-MM-DD/page_XXXXX.json
```

Run:

```powershell
python scripts\audit_saferproducts_benchmark.py
```

Do not modify the benchmark based on assumptions. Review the audit first.
