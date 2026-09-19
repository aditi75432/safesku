# SafeSKU product mode

The demo is intentionally interactive rather than a screenshot-like dashboard.

## What a judge can do

1. Search the recall catalog by recall number or product name.
2. Open any indexed recall and run an investigation.
3. Inspect the live investigation response: identity candidates, incident evidence, timeline, trace, and derived signals.
4. Make a real human-in-the-loop decision on a marketplace candidate: **Confirm match**, **Reject**, or **Needs review**. The UI sends this decision to the backend and re-renders the case.
5. Click an evidence ID to open the structured source record behind that finding.
6. Export the current investigation as JSON or CSV.
7. Review the investigation history for the current application session.

## Product boundary

The local/demo catalog is intentionally backed by the SafeSKU benchmark artifacts that have already been built. The interface should not imply that it is querying all of Amazon or all CPSC history live. The research corpus and the compact demo bundle are separate concerns.

## Winning demo narrative

The judge should be able to discover a case, investigate it, challenge the identity decision, inspect source evidence, and export the resulting case without the presenter touching the code. That demonstrates a product workflow rather than a static visualization.
