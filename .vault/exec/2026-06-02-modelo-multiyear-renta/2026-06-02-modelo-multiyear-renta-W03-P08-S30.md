---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:f16242d8a0fd9b483b6a335f9e417e3a35d184dc50275adbb43dd8c69b358af5'
step_id: 'S30'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M190 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/190.toml`

## Description

- Rebaseline stale-open M190 manifest row against the current split authorization registry.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the M190 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/190.toml` already declares modelo 190 with `renta_years = [2025, 2026]`, `evidence_class = "reconciliation"`, and the M190 enrolling test.
- The manifest row matches the current recorded two-year reconciliation test contract.
- No product code changed in this step.

## Notes

- This closes the M190 manifest enrollment row only.
