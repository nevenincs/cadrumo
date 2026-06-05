---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S58'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P06.S58 - verify application live decomposition

Scope: `src/aeat/application/live/tests`, `src/aeat/entrypoints/cli/tests/test_live*`.

## Description

- Run ruff over the live facade, extracted filed-data helpers, extracted IVA remote-state model/outcome helpers, and focused live tests.
- Run filed-data capture/listing, IVA remote-state, live-read subgroup, and registry CLI tests.
- Confirm public `aeat.application.live` imports continue to expose moved DTOs and helpers.

## Outcome

Verification passed. Ruff reported no findings, and pytest reported 110 passing tests with one test deselected by marker selection.

## Notes

The live root remains above the final size target; residual service-family extraction remains tracked separately.
