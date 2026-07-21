---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S36'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M303 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/303.toml`

## Description

- Rebaseline stale-open M303 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M303 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/303.toml` already declares modelo 303 with `renta_years = [2025, 2026]`, `evidence_class = "calculation"`, and the M303 enrolling test.
- No product code changed in this step.

## Notes

- This closes the M303 manifest enrollment row only; it does not claim the legacy monolithic manifest path.
