# SafeSKU AWS deployment

This document deploys the current cloud product path:

```text
Browser
  │
  ├── small control requests ──> API Gateway HTTP API ──> Lambda
  │
  └── bundle bytes ────────────> S3 using a presigned PUT
                                      │
                                      ▼
                                Step Functions
                                      │
                                      ▼
                               Ingestion Lambda
                                      │
                                      ├── S3 workspace snapshot
                                      └── DynamoDB job/control state

Investigation Lambda/API
        │
        ├── S3 workspace snapshot
        ├── DynamoDB human review/history
        └── Amazon Bedrock + Strands
```

The design deliberately does not upload bundle bytes through API Gateway. AWS documents a 10 MB payload quota for HTTP APIs, while the SafeSKU demo bundle can be much larger. Presigned S3 upload keeps the data path independent from that API payload limit. citeturn546216search0turn546216search8

## Prerequisites

Install and authenticate:

```powershell
aws --version
sam --version
docker --version
aws sts get-caller-identity
```

Configure credentials if necessary:

```powershell
aws configure
```

Use a region where your account can invoke the selected Bedrock model. For this deployment the model is:

```text
us.amazon.nova-micro-v1:0
```

Amazon's current model documentation lists this inference profile and the in-region `amazon.nova-micro-v1:0` model ID. Current commercial-region Bedrock model access is enabled by default with the required AWS Marketplace permissions. citeturn546216search2turn546216search4

## Preflight in the repository

```powershell
pip install -r apps\api\requirements.demo.txt
pytest -q apps\api\tests
sam validate --template-file infra\template.yaml
```

## Build

From the repository root:

```powershell
sam build --template-file infra\template.yaml
```

Docker must be running because the public web/API function is packaged as a Lambda container image. AWS Lambda supports container images up to 10 GB uncompressed. citeturn546216search15

## Deploy

```powershell
sam deploy --guided --template-file .aws-sam\build\template.yaml
```

Use a stack name such as:

```text
safesku-demo
```

Keep the same region selected for Bedrock.

## What SAM creates

### SafeSkuDataBucket

Stores:

```text
incoming/<upload-id>/<bundle>.zip
snapshots/<job-id>/safesku.db
snapshots/<job-id>/overview.json
```

Browser uploads use a presigned PUT URL. AWS documents presigned URLs as a way to upload an object without giving the uploader AWS credentials. citeturn546216search8

### SafeSkuStateTable

On-demand DynamoDB stores:

```text
JOB#<job-id>
REVIEW#<recall-number>
HISTORY
WORKSPACE/CURRENT
```

DynamoDB on-demand is pay-per-request and automatically scales without capacity planning, which fits a hackathon workload that may be idle between demos. citeturn121098search2

### SafeSkuPipeline

A Standard Step Functions workflow calls the ingestion Lambda. Step Functions can orchestrate Lambda tasks and retries, and the AWS optimized Lambda integration is designed for this type of serverless workflow. citeturn121098search5turn121098search9

### SafeSkuIngestor

The ingestion worker has 10 GiB of Lambda ephemeral storage. Lambda supports configurable `/tmp` storage from 512 MiB to 10,240 MiB. citeturn121098search0

It:

```text
reads the S3 bundle
→ validates manifest/checksums
→ ingests records through WorkspaceService
→ checkpoints the SQLite WAL
→ uploads an immutable workspace snapshot
→ publishes WORKSPACE/CURRENT
```

### SafeSkuApi

This is the web console and API. It uses:

```text
FastAPI
Mangum
Strands Agents
Amazon Bedrock
```

## Get the public URL

```powershell
aws cloudformation describe-stacks `
  --stack-name safesku-demo `
  --query "Stacks[0].Outputs" `
  --output table
```

Open the `SafeSkuApiUrl` value.

## First cloud demo

1. Open the SafeSKU URL.
2. Go to **Data workspace**.
3. Choose **Add a SafeSKU data bundle**.
4. Upload `data\bundles\safesku-judge-bundle.zip`.
5. Wait for the cloud job to reach `completed`.
6. Open **Investigator**.
7. Search `22754`.
8. Run the investigation.
9. Confirm the agent badge shows the Bedrock/Strands mode.
10. Open an evidence item.
11. Make a human review decision.
12. Refresh and verify the decision persists.
13. Export the investigation.

## Important security notes

This template is a hackathon/demo deployment. Before a real internal deployment:

- restrict S3 CORS to the actual web origin instead of `*`
- add user authentication and authorization
- scope Bedrock permissions to the approved model/inference profile
- add dataset retention and deletion policies
- add KMS-managed encryption if required by the target organization
- place the search/data plane behind the organization's network controls where appropriate
- add CloudWatch alarms and structured application metrics
- replace the compact SQLite snapshot strategy with a managed query/search data store for high concurrency

## Why OpenSearch is not in this first AWS stack

SafeSKU already treats OpenSearch Serverless as the next scale-out search layer. AWS currently documents Search and Vector Search collection types, with serverless scaling and managed lifecycle. citeturn546216search1turn546216search3turn546216search9

For the hackathon deployment, SQLite snapshots keep the stack smaller and easier to operate. The application boundary is already separated so OpenSearch can replace the snapshot-query layer without changing the product workflow.

## Tear down after the demo

```powershell
aws cloudformation delete-stack --stack-name safesku-demo
```

The stack deletes the demo bucket and control table. Back up any dataset you want to retain before deleting the stack.
