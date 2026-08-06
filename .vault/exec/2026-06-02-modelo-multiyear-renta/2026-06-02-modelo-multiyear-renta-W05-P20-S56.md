---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:56f078b952bf7de5e02128fd1ce4673eb87527b2263fecf702c93ef6653c6074'
step_id: 'S56'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# reconcile the M200 authorization manifest entry with renta_years matching the recorded year-set

## Scope

- `src/aeat/_data/registry/aeat/authorization.d/200.toml`

## Description

- Rebaseline stale-open M200 manifest row against the current split authorization registry.
- Ground the check with RAG-first W04-W05 discovery and targeted reads of the M200 authorization fragment.
- Update the plan row to the current `authorization.d` entry.

## Outcome

- `authorization.d/200.toml` already declares the M200 two-year calculation enrollment contract.
- No product code changed in this step.

## Notes

- This closes the M200 manifest enrollment row only.
