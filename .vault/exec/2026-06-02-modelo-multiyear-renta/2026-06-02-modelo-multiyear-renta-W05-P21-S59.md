---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:5e45b554b00928dff7d09e5257d76c69f757b9a0b678b28f4dd84c83ddbdbd01'
step_id: 'S59'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M202 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/202.toml`

## Description

- Rebaseline stale-open M202 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M202 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/202.toml` already declares the M202 two-year calculation enrollment contract.
- No product code changed in this step.

## Notes

- This closes the M202 manifest enrollment row only.
