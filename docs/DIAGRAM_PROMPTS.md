# Prompts for Presentation-Quality SafeSKU Diagrams

## System architecture

Create a clean, high-end enterprise security and data-intelligence architecture
figure for a project called SafeSKU, "Evidence-grounded product safety intelligence
for online marketplaces." White background, restrained blue/charcoal professional
palette, rounded cards, thin lines, generous spacing, no decorative illustrations.
Show four real public sources on the left: CPSC recalls, SaferProducts.gov incidents,
Amazon marketplace metadata, and SafeSKU linkage artifacts. Flow into a normalization
and quality layer, then a central SQLite canonical workspace, then OpenSearch as the
retrieval index. To the right show a deterministic evidence and temporal engine,
then a Strands agent using a local Ollama model, then Cedar authorization, then a
human reviewer, then an auditable Safety Case. Label the key trust boundary:
"AI explains evidence; policy + human reviewer control protected actions." Use clear
arrows and small concise labels. Avoid logos and visual clutter.

## Investigation sequence

Create a polished horizontal sequence diagram for SafeSKU. Start with an
investigator searching CPSC recall #22754. Show four evidence retrieval steps:
official recall, marketplace candidates, public incidents, temporal timeline. Then
show a bounded Strands + local Ollama reasoning step, followed by Cedar denying
identity confirmation to the agent, followed by a human reviewer confirming or
rejecting the candidate, and finally an auditable Safety Case. Use a clean technical
conference style, white background, sparse typography, clear chronological arrows.

## Evidence graph

Create a technical evidence-graph visualization for SafeSKU. Center node is
"Official Recall". Connect it to "Marketplace Candidate", "Public Incident", and
"Hazard". Connect the marketplace candidate to identity evidence fields such as
UPC, brand, model, title similarity. Connect the public incident to incident date
and publication date, then to a "Pre-recall qualification" node. Connect all
qualified evidence to "Safety Case" and "Human Review". Use a clean research-paper
style with clear provenance labels and no decorative art.

## Trust boundary

Create a minimalist authorization architecture diagram for SafeSKU. Show an Agent
box with green ALLOW actions for search, read evidence, and summarize. Show red
DENY for "confirm marketplace identity" and "finalize safety case". Show a Human
Reviewer box with ALLOW for those protected actions. Place Cedar Policy between
agent/human actors and protected actions. Add a small audit trail node at the bottom.
Professional cloud-security visual language, white background, high readability,
no decorative imagery.
