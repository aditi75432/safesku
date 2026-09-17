# SafeSKU

Evidence-grounded product safety intelligence for online marketplaces.

SafeSKU connects public product-safety data with large-scale e-commerce review and product metadata to detect emerging safety signals, resolve affected product entities, and produce evidence-backed safety cases.

## Current project thesis

**Can cross-source temporal reasoning over consumer reviews, public safety reports, and official recalls identify emerging product-safety signals earlier and with fewer false positives than single-source approaches?**

## Data sources

- U.S. Consumer Product Safety Commission (CPSC) Recalls API
- SaferProducts.gov public incident data
- Amazon Reviews 2023 research dataset

## Repository layout

```text
safesku/
├── apps/
│   ├── api/              # FastAPI backend
│   └── web/              # Next.js frontend
├── data/
│   ├── raw/              # Never commit raw datasets
│   ├── interim/
│   └── processed/
├── docs/
│   ├── PROJECT_CHARTER.md
│   ├── DATA_STRATEGY.md
│   └── ARCHITECTURE_V0.md
├── infra/                # AWS/IaC
├── research/
│   ├── experiments/
│   ├── notebooks/
│   └── README.md
├── scripts/
└── tests/
```

## Engineering rules

1. No business logic inside route handlers.
2. No direct LLM calls from the frontend.
3. Every model-generated claim must carry evidence references.
4. Raw data is immutable and never committed to Git.
5. Every experiment is reproducible from a recorded configuration.
6. Never use future records when evaluating historical early-warning performance.
7. Prefer simple, typed modules over clever abstractions.

## First milestone

Build the CPSC recall ingestion pipeline and establish a small, leakage-safe research slice before adding any agent.
