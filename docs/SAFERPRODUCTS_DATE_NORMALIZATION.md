# SaferProducts date normalization fix

The historical audit found 23 records failing with `OSError: [Errno 22]
Invalid argument`. The failure occurs while converting OData `/Date(ms)/`
values using `datetime.fromtimestamp()`, which has platform-dependent range
behavior on Windows.

The normalizer now uses:

```text
UTC epoch + timedelta(milliseconds=...)
```

and treats an out-of-range date as an unavailable date field (`None`) rather
than rejecting the entire incident.

This preserves the incident record while making the problematic date explicit
through the normalized model.

## Recovery

No API re-download is required. Raw snapshots are already preserved.

After applying the fix:

```powershell
python -m pytest apps\api\tests -q
python scripts\ingest_saferproducts.py --start-date 2020-01-01 --end-date 2023-09-30 --page-size 100 --resume
```

The `--resume` flag reuses the existing raw monthly snapshots and rebuilds the
normalized corpus locally.
