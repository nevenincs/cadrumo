---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:964ba12d58455d1ba9a89fe72a5e880131fd666d2c5a99b620221d212c1984df'
step_id: 'S13'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Carry relation consumption channels into handoffs and prefill

## Scope

- `src/cadrumo/domain/calculations/registry/_handoffs.py`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `src/cadrumo/domain/calculations/registry/tests/test_relation_handoff_inventory.py`
- `src/cadrumo/application/calculations/_relation_prefill.py`
- `src/cadrumo/application/calculations/tests/test_relation_prefill_source_mesh.py`

## Description

- Preserve primary binding, alternate binding, formula relation, and formula binding as distinct sets in the canonical consumption index.
- Add the facade-exported ordered `relation_consumption_channels` projection and carry its result on every `RelationHandoffRecord`.
- Retarget the unresolved relation partition to the canonical index, channel projection, and consumption predicate.
- Delete the local formula-relation walker and declared-binding proxy, then re-point direct application tests to production authority.

## Outcome

- The bundled inventory measures 78 handoffs with no empty consumption-channel tuple; exact alternate-only and formula-relation-only records are proven.
- Fourteen focused handoff and prefill tests pass; Ruff, format, BasedPyright, collection, facade identity, structural, prohibited-construct, and diff gates are green.
- Formal review reported PASS with no actionable findings.
- Production and application changes landed in `0ac21bd662`; direct regression updates landed in `9809466c5f`.

## Notes

- The execution scaffold landed in broad concurrent commit `96b06b9b27`; this lifecycle commit completes it rather than rewriting shared history.
- The pre-existing applicability inventory hard count expects 108 rows while concurrent registry work now yields 156. That exact unrelated test remains red; no S13 behavior depends on the stale total.
