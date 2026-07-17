---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M180 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/180.toml`

## Description

- Rebaseline stale-open M180 manifest row against the current split authorization registry.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the M180 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/180.toml` already declares modelo 180 with `renta_years = [2025, 2026]`, `evidence_class = "reconciliation"`, and the M180 enrolling test.
- The manifest row matches the current recorded two-year reconciliation test contract.
- No product code changed in this step.

## Notes

- This closes the M180 manifest enrollment row only.
