---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S51'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M309 authorization manifest entry with calculation evidence_class and renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/309.toml`

## Description

- Rebaseline stale-open M309 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M309 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/309.toml` already declares `evidence_class = "calculation"` and the two-year M309 enrolling test.
- No product code changed in this step.

## Notes

- This closes the M309 manifest enrollment row only.
