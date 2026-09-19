# SafeSKU 3-minute demo story

## The story

SafeSKU is an **agentic product-safety investigator**. It connects official recalls, public safety incidents and marketplace identity evidence, then builds an auditable safety case.

## Hero case: Recall 22754

Use the hero case to show the temporal story:

1. A public SaferProducts incident was published on 2021-11-10.
2. The incident explicitly says the product was bought on Amazon and contains an Amazon product URL/ASIN.
3. The official CPSC recall is dated 2022-06-30.
4. The marketplace resolver has not independently confirmed the exact Amazon SKU from the metadata sample, so SafeSKU sends identity to human review instead of overclaiming.

This is the product principle: **evidence first, AI second**.

## Demo sequence

1. Open SafeSKU.
2. Click **Investigate 22754**.
3. Show the animated investigator trace.
4. Show the **232-day pre-recall signal**.
5. Show the direct marketplace reference extracted from the consumer narrative.
6. Show the marketplace candidates and the human-review boundary.
7. Open the evidence graph.
8. Switch to the 20111 example to demonstrate exact-identifier linkage.
9. End on the architecture: Lambda + API Gateway + Bedrock/Strands + compact evidence artifact.

## Do not say

- "The model predicted the recall."
- "The listing is definitely recalled" when the resolver is uncertain.
- "The AI proved causation."

## Say

- "SafeSKU found a pre-recall public association."
- "SafeSKU ranked marketplace identities using structured evidence."
- "When evidence is insufficient, the agent escalates to human review."
