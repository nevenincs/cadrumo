---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:504a8a069e1f6f4091b715ddb08146c74554a35a2b892f6a8701530a706e80bc'
step_id: 'S14'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# enumerate typed row assemblers and declared source-disposition ownership

## Scope

- `dev/source_connectivity/discovery.py`

## Description

- Derive every row-set grouping, closed grouping kind, dispatcher target, and typed observation return from the canonical assembler module.
- Project resolver ownership directly from the canonical live calculation-route declaration.
- Preserve multiple groupings routed to the same assembler without collapsing them.

## Outcome

The capability census now sees nine supported row groupings and every live resolver-owned binding source as independent structural facts. An assembler no longer implies resolver enrollment, and ownership no longer has to be reconstructed from scattered resolver classes.

## Notes

Ruff passed. The live scan retained both withholding groupings that intentionally share one assembler and projected 23 uniquely owned source kinds from `CALCULATION_ROUTE_RESOLVER_OWNERSHIP`.
