---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:672d000806a0e94cb33380b9440217b8349c33bf2aee1814ac61e535ff9f002b'
step_id: 'S04'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Make binding-derived export layouts safe to scan repeatedly

## Scope

- `src/cadrumo/domain/calculations/registry/_export.py`
- `src/cadrumo/domain/calculations/registry/tests/test_casilla_field_kind_enrollment.py`

## Description

- Make fixed-selector binding-field derivation preserve an already materialized field for the same binding.
- Keep the existing row-selector idempotence behavior unchanged.
- Exercise the real bundled Modelo 720 layout through the production snapshot and re-derivation paths.
- Repair the owning row-binding fixtures to use the canonical closed `ExportEncoding.ASCII` member.

## Outcome

Binding-field derivation is idempotent across every bundled revision declaring an export layout, so later casilla-keyed classifiers may always derive first without duplicating M720 fields. The full owning module passed 5 tests, the real M720 registry suite passed 22 tests, and a production census found zero non-idempotent revisions among all 15 layout-bearing revisions. Ruff, Ruff format, BasedPyright, scoped diff checking, and `aeat app registry verify` passed. Formal re-review found no remaining issue.

## Notes

The first broader verification attempt exposed three pre-existing strict-enum fixture failures in the owning test module. They were corrected with the canonical enum rather than by weakening production validation or adding compatibility coercion. An unrelated export-exemption test still assumes a now-empty `FEEDS_ADDRESSED_CASILLA` population and was not changed in this step.
