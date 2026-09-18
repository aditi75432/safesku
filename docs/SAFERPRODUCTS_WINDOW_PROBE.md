# SaferProducts.gov filtered-window probe

This probe verifies the exact OData date-filter syntax needed before SafeSKU performs bulk incident ingestion.

## Why probe first?

The public API uses OData. SafeSKU should confirm the live service accepts the intended date filter and paging semantics before requesting a large historical window.

The research benchmark needs incident dates that can be compared against CPSC recall dates. Therefore the historical ingestion will use:

```text
IncidentDate >= window_start
IncidentDate < window_end
```

and the eventual pre-recall eligibility rule will be:

```text
incident_date < recall_date
AND publication_date < recall_date
```

The second condition prevents an incident that was only published after the recall from being treated as evidence available before the recall.

## Run

```powershell
python scripts\probe_saferproducts_window.py --start-date 2020-01-01 --end-date 2020-02-01
```

The probe requests only five records and asks the API for an inline total count.

Do not run the full historical ingestion until this probe succeeds.
