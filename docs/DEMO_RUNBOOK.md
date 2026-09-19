# SafeSKU 3-Minute Winning Demo Runbook

## Demo objective

The judge should understand the complete idea in one pass:

> SafeSKU takes real safety data from multiple public sources, resolves possible
> marketplace products, checks whether public evidence predates a recall, explains
> the evidence with a local agent, and prevents the agent from approving its own
> identity decision.

The strongest story is **evidence first, AI second**.

## Recording setup

Before recording:

1. Start Docker, OpenSearch, Ollama, Cedar, and SAM locally.
2. Load the compact judge bundle.
3. Build the OpenSearch index.
4. Confirm the workspace is READY.
5. Preload the golden investigation for CPSC #22754.
6. Close unrelated windows and developer terminals.
7. Keep the browser at 100% zoom.

## Three-minute script

### 0:00 to 0:20: Problem

Say:

> Product recalls arrive after a product has already reached a marketplace. The
> hard part is not finding the recall. The hard part is connecting the recall to
> the right marketplace product and separating real prior safety evidence from
> noise.

### 0:20 to 0:40: One workspace

Show the SafeSKU home page.

Point to:

```text
1,005 recalls
13,696 public incidents
53,632 marketplace products
84,037 linkage candidates
```

Say:

> I loaded one portable SafeSKU bundle containing real public safety artifacts.

### 0:40 to 1:05: Recall search

Search:

```text
22754
```

Open the Mohnark Lidocaine recall.

Say:

> SafeSKU starts from the official recall and keeps source evidence separate from
> everything we infer.

### 1:05 to 1:30: Identity resolution

Open marketplace candidates.

Show:

```text
ASIN
Title
UPC
Brand
Model
Linkage features
Confidence / evidence score
```

Say:

> These are candidates, not confirmed matches. The score is evidence for identity,
> not a probability.

### 1:30 to 1:55: Temporal reasoning

Show the evidence timeline.

Say:

> A temporal signal only qualifies when both the incident date and the publication
> date are before the official recall date.

Never call this causal proof.

### 1:55 to 2:20: Agent

Show the Strands trace:

```text
search_cpsc_recall
find_amazon_candidates
get_saferproducts_incidents
build_safety_timeline
verify_evidence
```

Say:

> The local agent is not the source of truth. It reads the evidence and turns it
> into an investigation brief.

### 2:20 to 2:40: Cedar

Show:

```text
Agent: CONFIRM_IDENTITY -> DENY
Human reviewer: CONFIRM_IDENTITY -> ALLOW
```

Say:

> The agent can investigate, but it cannot approve the marketplace identity it just
> proposed. Cedar enforces that separation.

### 2:40 to 2:55: Human review

Click a candidate and select a decision.

Say:

> A reviewer can confirm, reject, or defer the candidate, with an auditable reason.

### 2:55 to 3:00: Safety Case

Export the case.

Finish with:

> SafeSKU turns four public data sources into one evidence-backed safety case,
> without giving the model permission to decide what the evidence means.

## Recording rule

Do not narrate implementation details such as package versions, installation
commands, stack traces, or debugging. The three-minute video is about the problem,
the insight, the working product, and why the trust boundary matters.
