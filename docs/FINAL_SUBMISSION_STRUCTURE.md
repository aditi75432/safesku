# Final Submission Structure

## Repository root

```text
safesku/
├── README.md
├── apps/
├── infra/
├── scripts/
├── data/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_SOURCES.md
│   ├── DEMO_RUNBOOK.md
│   ├── DIAGRAMS.md
│   ├── DIAGRAM_PROMPTS.md
│   ├── GITHUB_RELEASE_CHECKLIST.md
│   ├── RESEARCH_EVALUATION.md
│   ├── RESULTS.md
│   └── USER_MANUAL.md
└── tests/
```

## Judge-facing message

**SafeSKU does not ask an LLM to decide whether a marketplace product is the recalled
product. It builds an evidence trail first, lets the agent explain that trail, and
uses Cedar plus human review to control the irreversible decision.**
