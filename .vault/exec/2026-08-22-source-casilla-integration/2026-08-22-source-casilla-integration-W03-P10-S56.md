---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2f04ed94382ca471fc917f033f52d424bc0047c32e25e363679232cc8d918f9c'
step_id: 'S56'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-amortization-casilla-grounding-research]]"
---

# ground amortization destinations, revision windows, eligible basis, rates, limits, and asset grain

## Scope

- `.vault/research/2026-08-23-amortization-casilla-grounding-research.md`

## Description

- Verified the 2025 Modelo 100 activity destinations against the official form and AEAT guidance.
- Traced the persisted asset and amortization ledger fields, validation boundaries, and absent production calculation service.
- Located the existing transaction-ledger authority for box 0208 and classified it as a competing evidence path.
- Compared activity amortization with the separate finca amortization calculation and destination.
- Recorded the supported revision window and the decisions that must remain with the ADR.

## Outcome

The research establishes 0208 and 0227 as the 2025 material and intangible activity-amortization destinations, while finca amortization remains a distinct 0131 source contract. The current asset ledger is insufficient filing proof, and 0208 already has a transaction-ledger claimant, so implementation must decide authority replacement and collision behavior rather than sum the two paths.

## Notes

Earlier revisions and the complete legal treatment of special amortization elections remain intentionally ungrounded. No production code or registry binding was changed in this research step.
