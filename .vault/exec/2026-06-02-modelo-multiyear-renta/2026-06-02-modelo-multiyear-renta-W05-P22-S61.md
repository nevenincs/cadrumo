---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S61'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M232 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/232.toml`

## Description

- Rebaseline stale-open M232 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M232 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/232.toml` already declares the M232 two-year data-fidelity enrollment contract.
- No product code changed in this step.

## Notes

- This closes the M232 manifest enrollment row only.
