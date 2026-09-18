# Historical SaferProducts ingestion

SafeSKU acquires public SaferProducts.gov incidents in bounded calendar-month windows.

## Pagination

The service is OData. The ingestion code does not depend on an `__next` continuation URL. It uses deterministic `$top` + `$skip` pagination and stops when the returned page is smaller than the requested page size.

The query is ordered by:

```text
IncidentDate asc,IncidentReportNumber asc
```

## Raw-data preservation

Every API page is preserved as an immutable JSON snapshot under:

```text
data/benchmark/saferproducts/raw/YYYY-MM-DD/page_XXXXX.json
```

The processed canonical records are stored in:

```text
data/benchmark/saferproducts/incidents.jsonl
```

and summarized in:

```text
data/benchmark/saferproducts/manifest.json
```

## Historical leakage rule

For pre-recall analysis, SafeSKU will count an incident as public evidence only when:

```text
incident_date < recall_date
AND
publication_date < recall_date
```

This distinguishes the date the safety event occurred from the date the incident became publicly available.

## Example

```powershell
python scripts\ingest_saferproducts.py --start-date 2020-01-01 --end-date 2020-02-01 --page-size 100
```

Only after the small-window run is validated should the full 2020-01-01 through 2023-09-30 benchmark be ingested.
