---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:c5de31a49da4584b1482ea789845802102ea177382eb7d3769efd9ec35314e45'
step_id: 'S32'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-inventory-casilla-mapping-adr]]"
---

# adjudicate the mapping from opening stock, purchase movements, and closing stock to 0177, 0181, and 0182

## Scope

- `.vault/adr/2026-08-23-inventory-casilla-mapping-adr.md`

## Description

- Adopt the complete acquisition-cost projection for casilla 0181.
- Split closing-minus-opening variation by sign across casillas 0177 and 0182.
- Require mutual exclusion and retain the taxpayer-year-activity source grain.
- Reject the stale signed casilla 0155 projection without compatibility behavior.

## Outcome

The accepted inventory ADR now defines the authoritative 2025 three-output mapping. It prevents the existing IVA-exclusive subtotal from claiming casilla 0181 and prevents one signed variation from being misrouted or double-presented.

## Notes

Source completeness, continuity, absence, and override policy are recorded by the same ADR and closed separately under Step S33.
