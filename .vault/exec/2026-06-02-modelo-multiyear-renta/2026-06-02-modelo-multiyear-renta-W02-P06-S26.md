---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S26'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M100 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/100.toml`

## Description

- Rebaseline stale-open M100 manifest row against the current split authorization registry.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the M100 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/100.toml` already declares modelo 100 with `renta_years = [2024, 2025]`, `evidence_class = "calculation"`, and the M100 enrolling test.
- The manifest row matches the test's recorded two-year set.
- No product code changed in this step.

## Notes

- This closes the M100 manifest enrollment row only; it does not claim broader fleet completeness.
