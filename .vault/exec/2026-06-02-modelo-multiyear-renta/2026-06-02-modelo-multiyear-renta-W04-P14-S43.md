---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:29cc90d847b878ce8dafcc2fcef4904a35dc0c8dc57bb476fe48bb5af1f07a8f'
step_id: 'S43'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M353 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/353.toml`

## Description

- Rebaseline stale-open M353 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M353 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/353.toml` already declares the two-year M353 calculation enrollment contract.
- No product code changed in this step.

## Notes

- This closes the M353 manifest enrollment row only.
