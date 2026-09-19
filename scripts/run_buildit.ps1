$ErrorActionPreference = "Stop"

Write-Host "[1/4] Starting OpenSearch..."
docker compose -f infra\build-it\docker-compose.yml up -d

Write-Host "[2/4] Configuring local SafeSKU stack..."
$env:SAFE_SKU_BUILD_IT = "true"
$env:SAFE_SKU_CLOUD_MODE = "false"
$env:SAFE_SKU_AGENT_MODE = "local"
$env:SAFE_SKU_SEARCH_MODE = "opensearch"
$env:SAFE_SKU_ROLE = "reviewer"
$env:SAFE_SKU_OPENSEARCH_URL = "http://127.0.0.1:9200"
$env:SAFE_SKU_OLLAMA_HOST = "http://127.0.0.1:11434"
$env:SAFE_SKU_LOCAL_MODEL = "llama3.1"

Write-Host "[3/4] Checking local services..."
python scripts\check_buildit_stack.py

Write-Host "[4/4] Starting SafeSKU with SAM Local..."
sam build --template-file infra\build-it\template.yaml
sam local start-api --template .aws-sam\build\template.yaml --warm-containers eager
