---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:c44b7822182a3a91903c85539030493e4d78b1c3c708d19a57f8fe086c3c5c6b'
step_id: 'S28'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M131 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/131.toml`

## Description

- Rebaseline stale-open M131 manifest row against the current split authorization registry.
- Ground the check with RAG-first W02-W03 discovery and targeted reads of the M131 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/131.toml` already declares modelo 131 with `renta_years = [2024, 2025]`, `evidence_class = "calculation"`, and the M131 enrolling test.
- The manifest row matches the current recorded two-year test contract.
- No product code changed in this step.

## Notes

- This closes the M131 manifest enrollment row only.
