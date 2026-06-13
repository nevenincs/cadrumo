---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P14.S48'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P14.S48 - Consolidate GROi and NIF IVA oracle driver flow

Scope: Reduce duplicated verdict/replay flow between the GROI and AEAT NIF-IVA
registry checker oracles.

## Description

- Add `_checker_oracle_flow.py` for shared verdict-map normalization, replay
  local-operation construction, replay observation decoding, observed-value
  lookup, and verdict comparison.
- Route `GroiOracle` and `AeatNifIvaCheckerOracle` through the shared helpers.
- Preserve oracle ids, surface kinds, planned operation ordering, guard
  behavior, replay payload shape, and per-oracle error messages.

## Outcome

GROI and AEAT NIF-IVA checker oracles now share the repeated replay/verdict
driver mechanics while retaining their distinct URL plans and policy semantics.

## Notes

The worktree already contained adapter live-driver docstring edits under
`src/aeat/adapters/outbound/aeat/sede/_groi_check.py`; this step leaves that
adapter WIP uncommitted. `just audit-duplication` dropped the domain oracle
flow clones but still reports an import-block clone between the two oracle
modules and adapter live-driver clones outside this slice.

Follow-up test hardening adds direct coverage for `_checker_oracle_flow.py`
using the real `GroiObservation` model, alongside the existing GROI/NIF-IVA
oracle-suite coverage.
