# SafeSKU User Manual

## 1. Start the local stack

Open PowerShell in the repository root and activate the virtual environment.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Verify infrastructure:

```powershell
Invoke-RestMethod "http://127.0.0.1:9200"
Invoke-RestMethod "http://127.0.0.1:11434/api/tags"
cedar --version
sam --version
```

Start the local API:

```powershell
sam build --no-cached --template-file infra\build-it\template.yaml
sam local start-api --template .aws-sam\build\template.yaml --warm-containers eager --no-watch
```

Then open:

```text
http://127.0.0.1:3000
```

## 2. Load the judge bundle

Use:

```text
data\bundles\safesku-judge-bundle.zip
```

The bundle contains compact, real artifacts for the demo workspace. The browser
uploads the ZIP in chunks, then SafeSKU validates the manifest and checksums and
runs local ingestion.

Expected ready state:

```text
CPSC recalls                 READY
SaferProducts incidents      READY
Amazon marketplace products  READY
SafeSKU linkage candidates   READY
```

## 3. Build the evidence index

Use the Pipeline action to build the local OpenSearch evidence index. The index
should eventually report a non-zero document count.

Verify from PowerShell:

```powershell
Invoke-RestMethod "http://127.0.0.1:9200/safesku-evidence/_count"
```

The current judge workspace has been validated at 153,870 indexed documents.

## 4. Investigate a recall

Search for:

```text
22754
```

Open the Mohnark Pharmaceuticals recall and choose **Investigate**.

SafeSKU shows:

- official CPSC facts
- marketplace identity candidates
- public consumer reports
- historical temporal relationships
- evidence IDs
- the investigation trace
- human-review posture
- a Safety Case export

## 5. Human review

A marketplace candidate is not a confirmed match just because it has a high
linkage score. A reviewer can select:

```text
MATCH
NON_MATCH
UNCERTAIN
```

and add a note. The decision is persisted as an audit event.

## 6. Common troubleshooting

### OpenSearch returns 404 for `safesku-evidence`

The index has not been built yet. Run the Pipeline index-building action and check:

```powershell
Invoke-RestMethod "http://127.0.0.1:9200/_cat/indices?v"
```

### Tests fail because search returns unrelated real data

Tests use temporary workspaces. The repository test configuration forces SQLite
search so a developer's global OpenSearch index cannot leak into tests.

### SAM still uses old code

Rebuild before starting SAM:

```powershell
sam build --no-cached --template-file infra\build-it\template.yaml
```

AWS documents that local SAM execution uses the built artifacts, and changes to
code require a rebuild when using `.aws-sam`. citeturn881224search1

### Amazon ingestion seems stuck

Check the workspace job rather than re-uploading repeatedly. The optimized local
path batches SQLite writes and runs ingestion outside the upload HTTP request.
