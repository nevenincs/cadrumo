---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:639783048911edade830b76ca1d492af93880ce8459748234a58070857a3a211'
step_id: 'S31'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-inventory-casilla-grounding-research]]"
---

# ground M100 inventory increase, purchases, and decrease semantics against official AEAT and BOE sources

## Scope

- `.vault/research/2026-08-23-inventory-casilla-grounding-research.md`

## Description

- Verify the 2025 annual Modelo 100 form against Orden HAC/277/2026.
- Ground stock variation and acquisition-cost semantics in the AEAT Renta 2025 manual.
- Compare the official facts with the encrypted inventory ledger and valuation engine.
- Identify unsafe gaps in purchase cost, cross-year continuity, closing authority, absence semantics, and revision coverage.

## Outcome

Official evidence supports activity-grained 2025 outputs for inventory increase at 0177, purchases at 0181, and inventory decrease at 0182. It rejects the dormant signed 0155 mapping. The existing variation primitive can be split by sign, but the current IVA-exclusive purchase subtotal cannot prove complete acquisition cost when indirect tax is non-recoverable or attributable costs are absent; the mapping ADR must close that gap before binding implementation.

## Notes

Only the 2025 revision is directly grounded. Earlier registry revisions remain outside the authorized implementation window until their annual authorities or an official continuity rule are verified.
