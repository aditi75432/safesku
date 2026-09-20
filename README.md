# SafeSKU
## Evidence-grounded product safety intelligence for online marketplaces

> **Turn a recall into an investigation.**  
> **Evidence first. AI second.**

[![Build It](https://img.shields.io/badge/First%20Commit-Build%20It-ff9900?style=flat-square)](#aws-build-it)
[![Local](https://img.shields.io/badge/runtime-local-1f2937?style=flat-square)](#quick-start)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab?style=flat-square)](#quick-start)
[![Tests](https://img.shields.io/badge/tests-104%20passed-2ea44f?style=flat-square)](#engineering-status)

SafeSKU is a local evidence and investigation system for marketplace product safety.

A recall tells a safety team **what was officially recalled**. It does not, by itself, answer the operational questions that come next:

- **Which marketplace listings could be the same product?**
- **Is there independent public safety evidence connected to that product?**
- **Did that evidence exist before the recall?**
- **What exactly supports the conclusion?**
- **Who is allowed to make the final identity decision?**

SafeSKU brings those steps into one reproducible workflow using official recall data, public consumer incident records, marketplace metadata, deterministic evidence processing, agent-assisted investigation, policy enforcement, and human review.

(SKU - Stock Keeping Unit)
---

## Why SafeSKU exists

Marketplace safety investigation is a cross-source problem.

Product names vary. Brands and manufacturers are inconsistent. Identifiers may be missing. Public incident reports and recalls have different timestamps. A model can explain evidence, but an explanation is not evidence.

SafeSKU is designed around that distinction:

> **The system can investigate uncertainty. It cannot turn uncertainty into authority.**

The workflow separates:

**Source evidence** → **identity candidates** → **temporal qualification** → **investigator explanation** → **human decision** → **auditable safety case**

That makes SafeSKU useful not as a chatbot, but as an **investigation layer for marketplace trust and safety teams**.

---

# What SafeSKU does

### 1. Ingest
Bring together heterogeneous safety and marketplace sources:

- **CPSC (U.S. Consumer Product Safety Commission) recalls** — official product recall records
- **SaferProducts.gov incidents** — public consumer incident reports
- **Amazon Reviews 2023 metadata** — marketplace product attributes
- **SafeSKU linkage artifacts** — precomputed candidate relationships

### 2. Build an evidence workspace
Normalize, validate, de-duplicate, and register records into a canonical local workspace.

### 3. Resolve product identity
Generate and rank marketplace candidates using structured identity evidence such as:

- UPC(Universal Product Code) agreement
- product-name overlap
- token rarity
- brand / model / manufacturer signals
- lexical similarity
- candidate-level feature combinations

A linkage score is used for **ranking**, not treated as a calibrated probability of identity.

### 4. Reason over time
A public incident is considered **pre-recall** only when both timestamps satisfy:

```text
incident_date < recall_date
AND
publication_date < recall_date
```

This prevents a later-published report from being presented as evidence of an earlier warning.

### 5. Explain the investigation
The Strands investigator retrieves the relevant evidence, summarizes it, cites evidence IDs, and prepares structured findings.

### 6. Govern the decision
The agent can investigate.

The reviewer decides.

Cedar protects the boundary between those two roles.

### 7. Produce a safety case
The final investigation can be reviewed, persisted, audited, and exported as structured JSON or CSV.

---

# The 3-minute product story

SafeSKU is easiest to understand through a single workflow:

```text
Select a recall
      ↓
Find marketplace candidates
      ↓
Retrieve public safety evidence
      ↓
Apply strict temporal rules
      ↓
Explain the evidence
      ↓
Human reviews the candidate
      ↓
Persist the decision
      ↓
Export a Safety Case
```

This is the product: **one recall in, one traceable investigation out.**

---

# See the system

## Architecture

<img width="1942" height="809" alt="Architecture" src="https://github.com/user-attachments/assets/8c59ff41-f3ff-4cc6-ac13-4c133be1aba7" />


### The design in one sentence

**Real safety data enters a local evidence plane; deterministic systems establish what can be supported; AI explains the evidence; Cedar and human review control protected decisions.**

The architecture deliberately separates:

- **Canonical state** — SQLite
- **Evidence retrieval** — OpenSearch
- **Deterministic analysis** — identity + temporal engine
- **Agent orchestration** — Strands
- **Local model runtime** — Ollama
- **Authorization** — Cedar
- **Protected decision** — Human reviewer

> **AI explains evidence. Policy and humans control protected actions.**

---

# Evidence model

<img width="1024" height="572" alt="evidence" src="https://github.com/user-attachments/assets/4eb976fd-5ff7-4f40-9733-5bc2ef49e149" />


Every investigation is assembled from structured records instead of free-form model memory.

Typical evidence objects include:

```text
E-CPSC-<recall>
E-SP-<incident>
E-AMZ-<candidate>
```

The evidence graph connects:

- official recalls
- marketplace products
- linkage candidates
- timeline events
- public incidents
- human review decisions
- Cedar authorization outcomes
- the resulting Safety Case

Every displayed finding is intended to remain traceable to one or more evidence IDs.

---

# How one investigation runs


<img width="1024" height="572" alt="investigation" src="https://github.com/user-attachments/assets/51507905-0d2e-4cc3-b753-8cfce04c672b" />


A typical request follows this sequence:

1. Browser sends a recall investigation request.
2. SAM Local routes the request into the application.
3. The evidence engine retrieves canonical records.
4. OpenSearch retrieves relevant indexed evidence.
5. Marketplace candidates are ranked.
6. SaferProducts records are retrieved.
7. Deterministic temporal rules qualify historical evidence.
8. The Strands investigator explains the evidence package.
9. Cedar evaluates protected actions.
10. The reviewer confirms, rejects, or defers a candidate.
11. The decision and audit trail are persisted into the Safety Case.

The important detail is the ordering:

> **Evidence retrieval and deterministic analysis happen before the model explanation.**

---

# Trust boundary

<img width="1024" height="572" alt="trust" src="https://github.com/user-attachments/assets/f1bcd6d5-979b-4818-8131-633cdbcabda7" />


SafeSKU explicitly separates **reasoning authority** from **decision authority**.

### Agent

**ALLOW**
- Read evidence
- Investigate
- Rank candidates
- Prepare findings

**DENY**
- Confirm marketplace identity

### Human reviewer

**ALLOW**
- Review evidence
- Confirm identity
- Reject identity
- Defer for further investigation

This is enforced as a policy boundary rather than being left to model behavior.

> **AI can reason over evidence. AI cannot grant itself authority.**

---

# AWS Build It

SafeSKU is designed for the **First Commit Build It** workflow, using AWS open-source technologies in a local setup.

| Technology | What SafeSKU uses it for |
|---|---|
| **AWS SAM Local** | Local API Gateway / Lambda emulation |
| **Amazon OpenSearch** | Evidence indexing and retrieval |
| **Strands** | Investigation agent orchestration |
| **Cedar** | Authorization and protected-action policy |
| **Ollama** | Local model runtime |
| **SQLite** | Canonical transactional workspace |

The application is intentionally runnable locally for the Build It workflow. No cloud deployment is required for the demo path.

### Why these technologies are separated

**SQLite is the source of truth.**  
**OpenSearch is the search layer.**  
**Deterministic code establishes the evidence state.**  
**The agent explains that state.**  
**Cedar protects the decision boundary.**

This keeps the architecture reproducible and makes the role of each AWS/open-source component visible.

---

# Data workspace

The current competition judge bundle contains:

| Dataset | Records |
|---|---:|
| CPSC recalls | **1,005** |
| SaferProducts incidents | **13,696** |
| Marketplace products | **53,632** |
| Supplied linkage candidates | **84,037** |
| OpenSearch evidence documents | **153,870** |

Large source datasets are intentionally kept outside Git. The repository contains application code, reproducibility tooling, selected evaluation artifacts, and a compact demo workspace.

---

# A real investigation example

The demo uses **CPSC #20163**, a recall concerning banned lawn dart sets.

SafeSKU does not simply take the highest-ranked marketplace result and declare it affected.

Instead, the investigation surface shows:

- the official recall
- ranked marketplace candidates
- linked public incidents
- strict pre-recall qualification
- an evidence timeline
- the agent trace
- the investigation posture
- the reviewer queue
- exportable findings

For this case, the workspace may surface a candidate with a **1.000 linkage score** while the product description is clearly inconsistent with the recalled item.

That is a feature of the safety design, not a failure of the workflow:

> **A ranking signal is not automatically a confirmation.**

The reviewer can leave the candidate unreviewed, reject it, or defer it instead of allowing an unsupported identity claim to become a safety decision.

---

# Deterministic temporal reasoning

SafeSKU separates **event time** from **model time**.

For an incident to qualify as pre-recall evidence:

```text
incident_date < recall_date
AND
publication_date < recall_date
```

Why both?

Because an incident may describe an event that happened earlier but only became publicly available after the recall.

SafeSKU therefore refuses to call that incident an earlier public warning.

This makes lead-time calculations reproducible and reduces temporal leakage during historical evaluation.

---

# Human review workflow

Candidate states:

```text
UNREVIEWED
NEEDS_REVIEW
CONFIRMED
REJECTED
```

The workflow is intentionally conservative:

```text
Candidate found
      ↓
Evidence reviewed
      ↓
Human decision
      ↓
Decision persisted
      ↓
Audit trail
```

The agent does not receive the authority to convert a ranked candidate into a confirmed marketplace identity.

---

# Research foundation

The product is also an evaluation environment for a deeper research question:

> **Can cross-source temporal reasoning over consumer incidents, official recalls, and marketplace identity evidence identify emerging product-safety signals earlier, while reducing false positives compared with single-source approaches?**

SafeSKU is structured to support comparisons across:

- keyword / rule baselines
- BM25 / TF-IDF retrieval
- embedding retrieval
- supervised classifiers
- LLM-only reasoning
- full SafeSKU evidence fusion

### Evaluation dimensions

**Identity**
- Precision
- Recall
- F1
- False-match rate

**Safety signal detection**
- Precision
- Recall
- F1
- AUROC
- AUPRC

**Temporal usefulness**
- Safety lead time
- Chronological historical replay

**Evidence quality**
- Evidence completeness
- Unsupported claim rate

**System behavior**
- Latency
- Retrieval performance

Chronological splits should be used for temporal evaluation to avoid future information leaking into historical analysis.

---

# Engineering principles

### Evidence before AI
The model receives curated evidence rather than becoming the source of truth.

### Candidate is not confirmed identity
Ranking and authorization are separate concerns.

### Time is part of the evidence
Historical claims use source timestamps, not model inference.

### The agent investigates; the reviewer decides
Protected identity actions are outside the agent's authority.

### Policy protects sensitive actions
Cedar encodes the decision boundary explicitly.

### SQLite is canonical; OpenSearch is retrieval
Search acceleration never replaces canonical state.

### Large data stays outside Git
The repository stays portable while the full judge bundle remains reproducible locally.

### Demo mode is deterministic
The competition demo can be replayed against the same workspace and evidence bundle.

---

# Quick start

## Prerequisites

- Python 3.12+
- Docker
- AWS SAM CLI
- OpenSearch
- Ollama
- Cedar CLI

## Validate

```powershell
sam validate --template-file infra/build-it/template.yaml --region ap-south-1
```

## Build

```powershell
sam build --no-cached --template-file infra/build-it/template.yaml
```

## Start locally

```powershell
sam local start-api `
  --template .aws-sam/build/template.yaml `
  --warm-containers eager `
  --no-watch
```

For the complete competition setup, data preparation, OpenSearch indexing, bundle loading, and recording flow, see:

```text
docs/DEMO_RUNBOOK.md
```

---

# Repository structure

```text
SafeSKU/
├── apps/
│   └── api/
│       ├── app/                 # application and domain logic
│       └── tests/               # automated tests
│
├── infra/
│   └── build-it/                # AWS SAM local infrastructure
│
├── policies/                    # Cedar authorization policies
├── scripts/                     # ingestion, indexing, evaluation, tooling
│
├── docs/
│   ├── images/                  # architecture and evidence diagrams
│   ├── DEMO_RUNBOOK.md
│   ├── DATA_SOURCES.md
│   └── DATA_LICENSES.md
│
├── data/
│   ├── demo/                    # compact demo artifacts
│   └── benchmark/               # selected evaluation artifacts
│
└── README.md
```

---

# Data sources and attribution

SafeSKU uses:

- **U.S. Consumer Product Safety Commission (CPSC)** recall data
- **SaferProducts.gov** public incident data
- **Amazon Reviews 2023** metadata distributed by the McAuley Lab / UCSD research dataset

Before redistributing or extending source datasets, review:

```text
docs/DATA_SOURCES.md
docs/DATA_LICENSES.md
```

The repository does not attempt to redistribute the full underlying source datasets.

---

# Engineering status

The local Build It implementation has been exercised against the SafeSKU judge bundle and a **153,870-document OpenSearch evidence index**.

Automated test suite:

```text
104 passed
2 warnings
```

The system has been built to be deliberately conservative about product identity and causal claims.

> **SafeSKU is an investigation aid. It is not a replacement for formal product-safety review.**

---

# What makes SafeSKU different

Most safety workflows stop at:

```text
Recall found → Search products → Show a result
```

SafeSKU goes further:

```text
Recall
  ↓
Identity resolution
  ↓
Independent incident evidence
  ↓
Strict historical qualification
  ↓
Evidence-backed explanation
  ↓
Policy enforcement
  ↓
Human review
  ↓
Auditable Safety Case
```

The goal is not to make the AI sound certain.

The goal is to make the investigation **traceable, reproducible, and safe to act on**.

---

## AI assistance

AI tools (ChatGPT & Gemini) were used during development for ideation, debugging assistance,
documentation refinement, and visual asset generation. The application
logic, evaluation pipeline, data processing, infrastructure configuration,
and final integration were reviewed and assembled by the project author.

## SafeSKU

### **Find the product. Check the evidence. Keep the decision accountable.**

