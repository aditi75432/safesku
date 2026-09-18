# Exact UPC temporal audit

An exact UPC intersection is strong identity evidence, but it is not enough
to establish that a safety report could have contributed to a pre-recall
signal.

For SafeSKU's historical benchmark, a qualifying pre-recall public incident
must satisfy:

```text
incident_date < recall_date
AND
publication_date < recall_date
```

This audit separates exact-UPC pairs into:

- `pre_recall_public`
- `pre_incident_published_after_recall`
- `incident_on_or_after_recall`
- `insufficient_dates`

The output is diagnostic only. It does not create ground-truth labels for
the full entity-resolution task.
