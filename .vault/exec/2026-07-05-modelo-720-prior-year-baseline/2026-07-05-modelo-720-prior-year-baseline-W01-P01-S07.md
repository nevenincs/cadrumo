---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S07'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---
# Clean stale threshold-axis registry comments beside the M720 deadline-window scaffold

## Scope

- `src/aeat/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/deadline_windows/0001-deadline_windows.toml`

## Description

- Updated the registry scaffold comment beside the Modelo 720 row-producer binding note from per-asset-class threshold wording to per-obligation-block threshold wording.
- Left deadline windows, parameters, legal refs, source refs, and registry values unchanged.

## Outcome

- The registry data comment no longer contradicts the block-level M720 threshold rule.
- Focused M720 aggregation tests and ruff checks passed after the change.

## Notes

- This was documentation-only registry data hygiene, not a schema or deadline change.
