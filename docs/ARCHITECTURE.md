# SafeSKU Architecture

## Design goals

SafeSKU is designed around five properties:

1. **Evidence-grounded**: source records remain the authority.
2. **Temporal correctness**: a signal is pre-recall only when both incident date and
   publication date precede the recall date.
3. **Identity uncertainty is explicit**: candidates are not silently promoted to
   confirmed marketplace SKUs.
4. **Agent actions are bounded**: the model reads evidence and explains it, but it
   does not own the final identity decision.
5. **Reproducible locally**: the Build It submission can run without an AWS account.

## Logical architecture

```mermaid
flowchart TB
    subgraph SOURCES[Public sources]
        CPSC[CPSC recalls]
        SP[SaferProducts.gov incidents]
        AMZ[Amazon Reviews 2023 metadata]
        LINK[SafeSKU linkage artifacts]
    end

    subgraph DATA[Evidence plane]
        ING[Schema detection + normalization]
        DB[(SQLite canonical workspace)]
        IDX[(OpenSearch evidence index)]
        RES[Identity resolution]
        TEMP[Temporal engine]
        PROV[Evidence provenance]
    end

    subgraph AI[Reasoning plane]
        TOOLS[Read-only investigation tools]
        STRANDS[Strands agent]
        OLLAMA[Local Ollama model]
    end

    subgraph TRUST[Trust plane]
        CEDAR[Cedar authorization]
        REVIEW[Human review]
        CASE[Safety Case + audit trail]
    end

    CPSC --> ING
    SP --> ING
    AMZ --> ING
    LINK --> ING
    ING --> DB
    DB --> IDX
    DB --> RES
    IDX --> TOOLS
    RES --> TEMP
    TEMP --> PROV
    TOOLS --> STRANDS
    OLLAMA <--> STRANDS
    STRANDS --> CEDAR
    CEDAR --> REVIEW
    REVIEW --> CASE
    PROV --> CASE
```

## Trust boundary

```mermaid
sequenceDiagram
    participant U as Investigator
    participant API as SAM Local API
    participant E as Evidence Engine
    participant A as Strands + Ollama
    participant C as Cedar
    participant H as Human Reviewer

    U->>API: Investigate recall
    API->>E: Retrieve evidence
    E-->>API: Facts + evidence IDs
    API->>A: Summarize evidence
    A-->>C: Request protected action
    C-->>A: DENY identity confirmation
    A-->>API: Draft investigation brief
    API-->>U: Candidate + evidence + review posture
    H->>C: Confirm identity
    C-->>H: ALLOW
    H->>API: Persist review decision
    API-->>U: Auditable Safety Case
```

## Canonical data model

```text
Recall
  ├── official facts
  ├── hazards
  └── recall date

SafetyIncident
  ├── incident date
  ├── publication date
  ├── product identity fields
  └── public narrative

MarketplaceProduct
  ├── parent ASIN
  ├── title
  ├── brand
  ├── model
  └── identifiers

IdentityCandidate
  ├── recall number
  ├── ASIN
  ├── linkage features
  ├── evidence score
  └── review status

EvidenceRecord
  ├── evidence ID
  ├── source
  ├── source record ID
  ├── kind
  └── event date

SafetyCase
  ├── recall
  ├── candidates
  ├── temporal findings
  ├── evidence IDs
  ├── authorization decisions
  └── human review
```

## Why SQLite + OpenSearch

SQLite remains the canonical local source of truth because the workspace is local,
portable, transactional, and easy to reproduce. OpenSearch is a retrieval/index
layer, not the authoritative store. This keeps the system simple while still
making the Build It search stack a real part of the application.

## Why the agent does not write identity decisions

Identity resolution has real uncertainty. The agent can gather and explain evidence,
but a high-level claim such as "this ASIN is the recalled product" must remain a
reviewable action. Cedar provides an explicit policy boundary between investigation
and approval.
