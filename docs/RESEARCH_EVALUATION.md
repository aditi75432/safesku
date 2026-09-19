# Research Evaluation Plan

## Research question

Can cross-source temporal reasoning over consumer reviews, public safety reports,
and official recalls identify emerging product-safety signals earlier and with fewer
false positives than single-source approaches?

## Contribution

The intended contribution is the combination of:

- cross-source product entity resolution
- temporal evidence fusion
- explicit evidence/provenance records
- leakage-safe historical replay
- human-review gating for uncertain marketplace identity
- bounded agentic explanation over deterministic evidence

The claim is deliberately narrower than "AI can detect unsafe products." The novelty
focus is on joining heterogeneous evidence while preserving identity uncertainty
and temporal provenance.

## Evaluation protocol

Use chronological splits for safety-signal evaluation. Never allow evidence from
a later date to influence a historical prediction window.

Primary metrics:

- identity precision / recall / F1
- false match rate
- safety-signal precision / recall / F1
- AUCPR / AUROC where meaningful
- safety lead time
- evidence completeness
- unsupported-claim rate
- end-to-end investigation latency

## Ablations

```text
Amazon only
CPSC only
CPSC + Amazon
+ temporal rules
+ product identity graph
full SafeSKU evidence fusion
```

## Lead-time definition

A public safety signal is considered pre-recall only when:

```text
incident_date < recall_date
AND
publication_date < recall_date
```

Lead time is:

```text
recall_date - earliest qualifying publication_date
```

This is an observational time difference. It does not prove causality or prediction.
