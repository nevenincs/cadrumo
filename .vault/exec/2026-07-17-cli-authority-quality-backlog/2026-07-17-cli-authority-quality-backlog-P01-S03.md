---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:7196f22a3313c5d389ada24fc466d8d114d0a6cb3a0469b5918d87f9d1b53bb8'
step_id: 'S03'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Prove historical as-of boundaries are honoured on the scoped path and refused explicitly on the unscoped path rather than silently ignored

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_queries.py`

## Description

- Add `test_unscoped_query_refuses_as_of_instead_of_silently_ignoring_it`: asserts `describe_modelo` / `casillas` / `bindings` / `formulas` on the unscoped period path raise `RegistryValidationError` (matching "as_of") when an `as_of` is passed, and that the same unscoped query still resolves WITHOUT `as_of` — so the refusal is scoped to the ignored argument, not a break of the path.
- Add `test_scoped_query_honours_the_as_of_validity_window`: resolves M100 2025/0A through the real authority to read the revision's `valid_from`, asserts the scoped `casillas_for_scope` resolves both with no as_of and with an as_of inside the window, and asserts an as_of before every declared window is honoured by refusing with `NoRevisionForPeriodError`.
- Import `date` and `NoRevisionForPeriodError`.

## Outcome

Real-behavior against the committed registry (no mocks, no synthetic tautology): the expected outcomes derive from `select_revision`'s documented `valid_from`/`valid_to` gating, which is the spec, not a hand-picked number. The pair proves the two halves of the honesty contract — scoped honours the as_of boundary, unscoped refuses it explicitly rather than silently ignoring it. 21 tests pass in the file; ruff clean.

## Notes

The scoped honouring proof is non-vacuous in both directions: an as_of INSIDE the window resolves and an as_of BEFORE every window refuses, so the test would fail if `as_of` were ignored (both would resolve) or over-rejected (both would refuse). git-diff-gated `test_queries.py` clean at HEAD before editing.
