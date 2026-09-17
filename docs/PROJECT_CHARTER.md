# SafeSKU Project Charter

## 1. Problem

Consumer product safety evidence is fragmented. Official recalls, public incident reports, and large volumes of consumer reviews contain related signals, but they do not naturally share a common product identity, vocabulary, or timeline.

The system should help a safety analyst answer:

> Which real product is this evidence about, what safety signal is emerging, how strong is the evidence, and how early could we have detected it?

## 2. What we are building

SafeSKU is an evidence-grounded safety intelligence system with five core capabilities:

1. Ingest public safety and recall data.
2. Ingest a research subset of Amazon Reviews 2023.
3. Resolve records to a canonical product/entity representation.
4. Detect and score temporal safety signals.
5. Produce an evidence card that a human can audit.

The agent is an interface and investigation orchestrator. It is not the source of truth.

## 3. Research contribution

The target contribution is **cross-source temporal safety reasoning**:

- product entity resolution across heterogeneous descriptions;
- temporal aggregation of safety-related evidence;
- explicit separation between observed evidence and model inference;
- leakage-safe historical replay to estimate safety lead time.

## 4. Hackathon product

The demo should replay a historical case and show:

real evidence -> product matching -> emerging signal -> evidence graph -> analyst case.

The primary demo must not depend on fabricated incidents.

## 5. Explicit non-goals

- Do not claim that a product is unsafe based only on an LLM response.
- Do not claim causal proof from reviews.
- Do not silently present model confidence as factual truth.
- Do not build a generic customer-service chatbot.
- Do not download the full Amazon Reviews 2023 corpus during the hackathon.

## 6. First research slice

Start with a narrow set of high-safety-relevance Amazon categories:

- Appliances
- Baby_Products
- Electronics
- Tools_and_Home_Improvement
- Toys_and_Games
- Automotive

The final category set can be revised only after measuring overlap with CPSC product families and obtaining a workable research slice.
