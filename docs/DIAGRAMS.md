# SafeSKU Diagram Set

These Mermaid diagrams are the source-of-truth diagrams for the repository and the
submission deck/video.

## 1. End-to-end architecture

```mermaid
flowchart LR
    subgraph SOURCE[Public evidence]
      A[CPSC]
      B[SaferProducts.gov]
      C[Amazon metadata]
      D[SafeSKU linkage]
    end
    SOURCE --> N[Normalize + validate]
    N --> DB[(SQLite workspace)]
    DB --> O[(OpenSearch)]
    DB --> X[Evidence + temporal engine]
    O --> X
    X --> S[Strands agent]
    S --> Q[Ollama local model]
    S --> CE[Cedar]
    CE --> HR[Human reviewer]
    HR --> SC[Safety Case]
```

## 2. Investigation sequence

```mermaid
sequenceDiagram
    participant I as Investigator
    participant R as Retrieval
    participant A as Agent
    participant P as Policy
    participant H as Human

    I->>R: Recall #22754
    R-->>I: Official recall + candidates + incidents
    I->>A: Investigate evidence package
    A->>R: Read-only tools
    R-->>A: Structured evidence
    A->>P: Protected identity action
    P-->>A: DENY
    A-->>I: Evidence-backed brief
    H->>P: Reviewer decision
    P-->>H: ALLOW
    H->>I: Safety Case
```

## 3. Evidence graph

```mermaid
flowchart TB
    R[Official Recall] --> P[Product Entity]
    P --> C[Marketplace Candidates]
    C --> I[Identity Evidence]
    R --> S[Safety Incidents]
    S --> T[Temporal Qualification]
    I --> E[Evidence Record]
    T --> E
    E --> H[Human Review]
    H --> SC[Safety Case]
```

## 4. Trust boundary

```mermaid
flowchart TB
    AG[Agent] -->|ALLOW| SEARCH[Search / investigate / summarize]
    AG -->|DENY| CONFIRM[Confirm marketplace identity]
    HR[Human reviewer] -->|ALLOW| CONFIRM
    CONFIRM --> AUDIT[Auditable decision]
```
