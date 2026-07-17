---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S38'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M390 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/390.toml`

## Description

- Rebaseline stale-open M390 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M390 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/390.toml` already declares the two-year M390 reconciliation enrollment contract.
- No product code changed in this step.

## Notes

- This closes the M390 manifest enrollment row only.
