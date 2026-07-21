---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S53'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M360 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/360.toml`

## Description

- Rebaseline stale-open M360 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M360 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/360.toml` already declares the M360 two-year data-fidelity enrollment contract.
- No product code changed in this step.

## Notes

- This closes the M360 manifest enrollment row only.
