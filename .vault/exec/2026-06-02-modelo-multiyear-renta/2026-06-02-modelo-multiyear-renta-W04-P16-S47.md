---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:f1590fa6d949ed343a3d20ef79d6d1a23d2a78b87285868e95c860a5c415b480'
step_id: 'S47'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M349 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/349.toml`

## Description

- Rebaseline stale-open M349 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M349 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/349.toml` already declares the M349 two-year data-fidelity enrollment contract.
- No product code changed in this step.

## Notes

- This closes the M349 manifest enrollment row only.
