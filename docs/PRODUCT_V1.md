# SafeSKU Product V1

## Product decision

SafeSKU is no longer designed around a fixed demo case list.

The product contract is:

> Upload safety and marketplace artifacts. SafeSKU profiles them, normalizes them, indexes them, builds product-identity candidates, joins public safety evidence, produces a traceable investigation, and routes uncertain identity decisions to a human reviewer.

The existing historical replay cases remain useful as regression/demo fixtures, but they are not the product's source of truth.

## User journey

```text
Upload artifacts
      |
      v
Profile + validate
      |
      v
Normalize into SafeSKU records
      |
      v
Index + fingerprint datasets
      |
      v
Generate product identity candidates
      |
      v
Join public incident evidence
      |
      v
Build temporal safety case
      |
      v
Agent investigates with read-only tools
      |
      v
Human review queue
      |
      v
Decision + evidence export
```

### Architecture diagram prompt

Create a clean enterprise architecture diagram for a product named **SafeSKU**, an Amazon marketplace product-safety intelligence platform. Use a white background, restrained blue/indigo accents, modern AWS architecture style, crisp vector lines, minimal rounded rectangles, no decorative gradients, no tiny unreadable text. Layout left-to-right in five layers: **Data Sources**, **Ingestion**, **Safety Intelligence**, **Agentic Investigation**, **Reviewer Experience**. Data Sources should show CPSC Recalls, SaferProducts.gov incidents, Amazon Product Metadata, and optional Amazon Reviews. Ingestion should show S3 object storage, schema detection, validation, normalization, and dataset fingerprinting. Safety Intelligence should show entity resolution, temporal reasoning, evidence graph, and review queue. Agentic Investigation should show Amazon Bedrock + Strands with read-only tools for recall lookup, candidate lookup, incident lookup, timeline building, and evidence verification. Reviewer Experience should show Search, Investigation Workspace, Human Review, and Export Safety Case. Use explicit arrows showing data provenance and a separate highlighted arrow from evidence stores into the agent. Add a small legend: **Evidence is source of truth. AI explains and orchestrates. Human review resolves ambiguity.**

## Local implementation

The local product uses SQLite because it is easy to run on Windows and gives us deterministic tests without requiring an AWS account for every developer run.

The workspace layer is isolated under:

```text
data/runtime/
  uploads/
  safesku.db
```

The SQLite store contains canonical tables for recalls, incidents, marketplace products, marketplace reviews, linkage candidates, human review decisions, datasets, and analysis jobs. FTS5 indexes provide fast local search.

The upload API streams files to disk rather than reading a whole marketplace artifact into memory. The accepted formats are CSV, JSON, JSONL, NDJSON, and their `.gz` variants.

## Supported artifact types

| Source | SafeSKU type | Purpose |
|---|---|---|
| CPSC recall export | `cpsc` | Official recall facts |
| SaferProducts export | `saferproducts` | Consumer incident evidence |
| Amazon product metadata | `amazon_products` | Marketplace identity resolution |
| Amazon Reviews 2023 review records | `amazon_reviews` | Review-level evidence when available |
| SafeSKU linkage candidates | `linkage` | Reuse benchmark-scale candidate/label artifacts |

## Evidence boundaries

SafeSKU must preserve four distinctions in the UI and API:

1. **Official recall fact**: sourced from CPSC.
2. **Consumer report**: sourced from SaferProducts.gov.
3. **Marketplace identity evidence**: a linkage observation, never causal proof.
4. **Derived temporal signal**: an ordering computed from the source dates.

The product must not claim that an Amazon review caused, predicted, or independently verified an official recall unless the underlying source evidence supports that exact statement.

## AWS target architecture

For the public hackathon deployment, use AWS as the real application platform rather than as a logo on the slide:

- **Amazon S3**: durable storage for uploaded raw artifacts. Browser uploads should use presigned URLs so large files do not pass through the API server. AWS documents presigned uploads for S3 and multipart upload for large objects. citeturn176024search3turn176024search10
- **AWS Step Functions**: orchestrate ingestion, normalization, linkage, evidence construction, and analysis stages. AWS SDK integrations let a state machine call AWS services directly, and optimized Lambda integration is available. citeturn176024search0turn176024search2
- **AWS Lambda + API Gateway**: stateless API and control plane for the interactive product.
- **DynamoDB**: metadata, review decisions, job status, and investigation summaries.
- **Amazon OpenSearch Serverless**: search/index layer for recalls, products, incidents, and later semantic evidence retrieval. OpenSearch Serverless provides search and vector-search collection types. citeturn176024search1turn176024search9
- **Amazon Bedrock + Strands**: evidence-grounded investigator. Bedrock supports application-side tool use, where the model requests a tool and application code executes it. Strands provides the agent orchestration layer and supports Bedrock models. citeturn433408search9turn433408search1
- **Amazon Bedrock AgentCore**: optional next step for managed agent runtime and observability. Current AWS documentation shows Strands agents running on AgentCore Runtime with CloudWatch/OpenTelemetry-based observability. citeturn433408search10

### AWS architecture diagram prompt

Create a premium AWS-native system architecture diagram for **SafeSKU**, with the AWS service icons accurate and readable. White background, subtle blue-gray grid, strong visual hierarchy, no clutter. Left side: user and uploaded marketplace/safety artifacts. First stage: **Amazon S3** receives raw artifacts using presigned upload URLs. Then a **Step Functions** workflow fans into Lambda workers for schema detection, normalization, entity resolution, and temporal analysis. Persist operational metadata and reviewer decisions in **DynamoDB**. Index searchable evidence documents in **OpenSearch Serverless**. On the right, an API Gateway + Lambda investigation API invokes an **Amazon Bedrock / Strands** agent with read-only tools. Draw a bold evidence flow from S3/DynamoDB/OpenSearch to the agent and a separate human-review loop back into DynamoDB. Place **SafeSKU Web Console** at the far right. Add CloudWatch monitoring underneath. Include a small security note: least-privilege IAM, encryption at rest, private service-to-service access where practical, no raw credentials in uploads. The visual message should be: **AWS runs the evidence pipeline; the agent operates on indexed evidence; humans make ambiguous identity decisions.**

## Why this architecture is intentionally split

Do not let the LLM perform ETL or become the database.

The deterministic pipeline creates stable evidence artifacts. The agent consumes those artifacts through small read-only tools. This makes the agent replaceable, testable, and auditable.

The same separation also helps the research evaluation. We can compare entity-resolution and temporal-signal methods independently from the language model.

## Next milestones

### V1.1, now

Dynamic local workspace: upload, stream ingest, source detection, dataset status, FTS search, generated candidates, investigation, persisted human review, review queue, and exports.

### V1.2

Replace local workspace search in AWS with S3 + DynamoDB + OpenSearch Serverless, while keeping the API contract stable.

### V1.3

Move bulk ingestion and analysis from in-process background jobs to Step Functions + Lambda. Large Amazon artifacts must never require the API container to hold the file in RAM.

### V1.4

Use Bedrock/Strands as the live investigator in the deployed environment. Capture actual tool-call traces and evidence references.

### V1.5

Add targeted Amazon review-text ingestion and safety-language aggregation for selected ASINs or categories. Do not describe metadata-only runs as review-text analysis.

