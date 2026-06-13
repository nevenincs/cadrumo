---
tags:
  - '#exec'
  - '#user-profile-lazy-import'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S07'
related:
  - "[[2026-06-03-user-profile-lazy-import-plan]]"
---

# Verify the lazy-loading gate is green end-to-end

## Scope

- `src/aeat/entrypoints/cli/test_lazy_command_tree.py`
- `src/aeat/application/user_profile/test_lazy_boundary.py`

## Description

- Run both files together against the post-P02 boundary.
- Re-run the application-package suite (115 tests) to confirm no
  consumer required adjustment under the new lazy-by-default
  contract.

## Outcome

- Producer-side probe at `test_lazy_boundary.py` is **green**: importing
  `aeat.application.user_profile` in a fresh interpreter places zero
  `aeat.domain.calculations.registry*` modules into `sys.modules`
  (down from 69 against the unfixed boundary). The application
  boundary itself is now lazy.
- The five originally-named CLI tests at `test_lazy_command_tree.py`
  **remain red**. The leak vector is orthogonal to the application
  boundary, recorded in the ADR's
  "Findings — execution-time scope expansion" section:
  `src/aeat/entrypoints/cli/_errors.py` (line 55) imports
  `StoredProfileDriftError` from `aeat.domain.user_profile`, whose
  `__init__.py` eagerly pulls `_registry_contract`. The 69-module
  leak is reproducible by importing only `aeat.entrypoints.cli._errors`
  in a fresh interpreter.
- `test_dispatching_a_subcommand_loads_its_module` stays green —
  on-demand wiring through `__getattr__` confirmed.
- All 115 user_profile package tests pass.

## Notes

- Plan's verification gate is not fully achieved: the producer-side
  contract is green and the application boundary is structurally
  correct, but the umbrella verification requiring all five CLI reds
  to pass is blocked on an orthogonal decision.
- A successor ADR (`2026-06-04-cli-errors-domain-package-lazy-import-adr`
  or equivalent) is required, picking among the three patterns the
  Findings section enumerates: lazy domain-package boundary, lazy
  consumer-side route to a registry-free error surface, or lifting
  `StoredProfileDriftError` up to the core layer.
- Per the dispatch brief, the half-fix pattern is explicitly avoided
  by not editing the CLI / domain surfaces under cover of the current
  ADR. The application-boundary fix landed honestly under its own
  ADR's scope, the orthogonal vector is fully diagnosed and recorded,
  and the follow-up campaign is well-scoped.
