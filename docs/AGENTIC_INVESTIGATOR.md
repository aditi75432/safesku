# SafeSKU Agentic Investigator

## Product definition

SafeSKU is an evidence-grounded product-safety investigator. A user gives the system a recall (or a natural-language investigation request). The system gathers structured evidence across the project's CPSC, SaferProducts.gov and Amazon artifacts, resolves marketplace candidates, constructs a temporal view, and returns a SafetyCase.

The LLM is not the source of truth. It is an investigation/orchestration and narrative layer. Structured evidence is returned by read-only tools and every displayed material finding carries evidence IDs.

## Tool loop

1. `search_cpsc_recall`
2. `find_amazon_candidates`
3. `get_saferproducts_incidents`
4. `build_safety_timeline`
5. `verify_evidence` / evidence-backed synthesis

In AWS mode, Strands + Amazon Bedrock supplies the narrative layer. If Bedrock is unavailable, the deterministic evidence workflow still produces a working prototype so the demo does not depend on a live model call.

## Safety/epistemic boundary

- CPSC records are treated as official recall facts.
- SaferProducts records are treated as consumer incident evidence.
- Amazon linkage is identity evidence, not causal evidence.
- A pre-recall public incident is a temporal observation, not proof that a recall was predicted.
- Scores shown in the UI are evidence-ranking signals, not calibrated probabilities.

## Local run

From the repository root:

```powershell
pip install -r apps\api\requirements.demo.txt
python scripts\build_safesku_demo_bundle.py
python -m uvicorn app.demo_app:app --app-dir apps\api --reload --port 8080
```

Open `http://127.0.0.1:8080`.

## AWS agent mode

Set:

```powershell
$env:SAFE_SKU_AGENT_MODE="bedrock"
$env:AWS_REGION="us-east-1"
$env:SAFE_SKU_BEDROCK_MODEL="us.amazon.nova-micro-v1:0"
```

The same endpoint then calls a Strands agent using read-only tools and Bedrock for synthesis. The structured result remains deterministic and evidence-backed.
