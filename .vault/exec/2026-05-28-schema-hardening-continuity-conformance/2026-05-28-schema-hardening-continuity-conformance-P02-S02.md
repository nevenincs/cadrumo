---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S02'
related:
  - '[[2026-05-28-schema-hardening-continuity-conformance-plan]]'
  - '[[2026-05-27-schema-hardening-casilla-continuity-contract-adr]]'
---

# `schema-hardening` `P02.S02`

Added generic retirement and unmatched-continuity validation semantics to the
strict cross-revision continuity policy.

- Modified: `src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- Created: `.vault/exec/2026-05-28-schema-hardening-continuity-conformance/2026-05-28-schema-hardening-continuity-conformance-P02-S02.md`
- Created: `.vault/audit/2026-05-28-schema-hardening-continuity-conformance-p02-s02-review.md`

## Description

Added strict-policy checks that validate declared continuity evolutions against
real casilla continuity surfaces for the referenced revision pair. A strict
evolution now reports a mismatch when the declared `continuidad_id` appears in
neither referenced revision.

Added strict retirement semantics for declared continuity surfaces. Adjacent
non-overlapping strict revision boundaries now require a `retired` evolution
when a source revision declares a `continuidad_id` and the target revision no
longer declares it. A `retired` evolution also fails when the source surface is
missing or the target surface is still present.

The implementation remains modelo-agnostic and keeps continuity semantics in
the validator policy layer. No schema, loader, or corpus TOML files were edited
in this step.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry/_validate_cross_revision.py`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_cross_revision_drift.py -q`

Both checks passed. The pytest run emitted the existing semantic-role singleton
warnings for M347; those warnings were present in the pre-change baseline and
are not authored by this step.

## Notes

S02 intentionally landed the validator implementation before S03 adds dedicated
real-behavior regression tests for `retired`, `repurposed`, and unmatched
continuity decisions.
