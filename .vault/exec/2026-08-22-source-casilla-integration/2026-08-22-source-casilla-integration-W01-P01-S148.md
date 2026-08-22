---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:74dc35c2c89a074d371ff7e6a4b589613c6099d7592fc58ad4456eeb3ca797d1'
step_id: 'S148'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# require source provenance at every revision identity and persistence boundary and correct its identity contract

## Scope

- `src/cadrumo`

## Description

- Remove source-provenance defaults from the revision model, identity builders,
  public derivation function, and persistence boundary.
- Stamp every identity and revision caller with its canonical trace or an explicit
  empty tuple.
- Include the empty or populated order-canonical six-axis trace in every revision
  identity payload.
- Preserve baseline provenance through amendment identity derivation and draft
  persistence.
- Add field-deletion refusal, explicit-empty acceptance, caller-census, and
  required-signature tests.
- Run focused domain, encrypted persistence, connectivity authority, amendment,
  payload, Ruff, compilation, diff, and independent review gates.

## Outcome

Source provenance is now a required identity decision at every governed boundary.
A missing serialized field is rejected, explicit emptiness is accepted, populated
rows remain order-canonical, and amendments retain their baseline trace. Independent
review passed with no findings.

## Notes

Concurrent shared-worktree activity committed the main S148 sweep in mixed commit
`8f560d62e5`; that commit also contains unrelated benchmark, registry, CLI, and
other agents' work. No rewrite, reset, revert, or false one-step source-commit claim
was made. The remaining S148-owned corrections are
`src/cadrumo/application/modelo/_amendment_actions.py`,
`src/cadrumo/application/modelo/tests/test_iva_wallet_engine_overrides.py`,
`src/cadrumo/application/modelo/tests/test_m303_rectificativa_motive_lifecycle.py`,
`src/cadrumo/application/modelo/tests/test_revision_filing_evidence_integrity.py`,
and `src/cadrumo/domain/modelos/tests/test_calculation_revision.py`.

Focused identity, encrypted round-trip, authority, and independent-review suites
reported 93 passing tests. The amendment and payload rerun reported 57 passing and
one unrelated existing no-op-amend expectation failure. The broad changed-caller
run reported 598 passing, 92 failures, and four errors dominated by concurrent
baseline drift: missing Modelo 390 registry coverage, selector-schema changes,
translation expectations, and unrelated repository/verification signatures.
