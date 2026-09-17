# SafeSKU Architecture v0

```text
                PUBLIC / RESEARCH DATA
          ┌──────────┬──────────┬──────────┐
          │          │          │          │
        CPSC      Safer       Amazon      Metadata
       Recalls   Products     Reviews
          │          │          │
          └──────────┼──────────┘
                     ▼
               Ingestion Layer
          validation + normalization
                     │
                     ▼
             Canonical Data Model
          recall / incident / review
                     │
            ┌────────┴────────┐
            ▼                 ▼
     Entity Resolution   Safety Signal
       candidate search    extraction
            │                 │
            └────────┬────────┘
                     ▼
             Evidence Graph
                     │
                     ▼
              Investigation API
                     │
                     ▼
                Web Console
```

## Design principle

The system separates:

**evidence** -> **derived signals** -> **model inference** -> **human decision**.

An LLM must never manufacture evidence. Every generated statement must reference stored evidence IDs.

## AWS target

For the deployed version:

- S3 for raw and processed objects
- Lambda for lightweight ingestion jobs
- Step Functions for multi-stage workflows
- DynamoDB for application state
- OpenSearch Serverless for lexical/vector retrieval
- Bedrock/Strands for investigation orchestration
- API Gateway for backend API exposure
- Amplify for the web application

AWS services are introduced after the local data pipeline is stable.
