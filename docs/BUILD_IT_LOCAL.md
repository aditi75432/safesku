# SafeSKU Build It track

SafeSKU is now designed to run entirely on a developer machine for the Build It track. No AWS account, card, or cloud deployment is required.

## Local stack

- **Strands Agents SDK** runs the investigation agent.
- **Ollama** hosts the local model used by Strands.
- **Cedar** enforces application actions such as identity-review approval.
- **AWS SAM Local** emulates the Lambda/API Gateway surface locally.
- **OpenSearch** provides the local evidence/product search layer.
- **SQLite** remains the canonical local workspace for structured joins and durable application state.

The official First Commit Build It track is explicitly for open-source AWS tooling on the local machine, including Strands, Cedar, SAM Local, and OpenSearch, with no AWS account, card, or bill required. The judging page also says the project is judged on impact, AWS usage, learning, execution, and the three-minute demo. See the event page before submission for any last-minute changes.

## Start here

1. Install Ollama and pull the configured local model.
2. Install the Cedar CLI for policy validation and install the Python Cedar binding used by the application.
3. Start OpenSearch with Docker Compose.
4. Import the SafeSKU judge bundle through the UI.
5. Build the OpenSearch evidence index.
6. Run the API through SAM Local.

### One-time installs

Ollama official Windows installer:

    irm https://ollama.com/install.ps1 | iex

Then:

    ollama pull llama3.1

Strands' Python integration supports Ollama-hosted local models and tool/function calling.

Cedar CLI on Windows can be installed from the official Cedar release installer. SafeSKU uses the Cedar policy file at `policies/safesku.cedar` and the Python binding for runtime authorization.

Install Python dependencies:

    pip install -r apps/api/requirements.demo.txt

## OpenSearch

OpenSearch runs only for local development. The included Compose file disables the security plugin for this localhost-only test environment.

    docker compose -f infra/build-it/docker-compose.yml up -d

Check:

    python scripts/check_buildit_stack.py

Index the current SafeSKU workspace:

    python scripts/index_workspace_opensearch.py

The script reads the durable workspace database and indexes recalls, incidents, marketplace products, and linkage candidates into one searchable SafeSKU evidence index.

## SAM Local

Build the Lambda container:

    sam build --template-file infra/build-it/template.yaml

Start the local API:

    sam local start-api --template .aws-sam/build/template.yaml --warm-containers eager

AWS SAM Local runs Lambda functions behind a local HTTP server, which is the local equivalent of the API Gateway + Lambda boundary we would use in a cloud deployment.

## Local agent

SafeSKU uses Strands with Ollama. The model is a local process at `http://127.0.0.1:11434`. The agent is read-only and can call:

- search CPSC recall
- retrieve marketplace candidates
- retrieve SaferProducts incidents
- build the safety timeline

Cedar does not authorize the agent to make the human identity decision. The review action is reserved for the reviewer role.

## Judge story

The three-minute demo should be:

1. Upload one SafeSKU bundle.
2. Show automatic dataset detection and counts.
3. Search for a recall.
4. Run an investigation with the local Strands agent.
5. Show the evidence timeline and OpenSearch-backed search.
6. Open a marketplace candidate.
7. Attempt or perform a human identity decision through the Cedar policy gate.
8. Export the safety case.
9. Briefly show the local AWS stack: SAM Local + Strands + Cedar + OpenSearch.

The product is not a collection of hardcoded cases. Historical replays remain useful as smoke tests, but the main path runs against the imported workspace.
