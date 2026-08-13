---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:b4ac431426d08122bfc88b97e188fe3e23d897390db5a7687005cccf75bf1e7c'
step_id: 'S57'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# confirm `test_json_schema_conformance.py`'s existing key-parity gate still passes and add a note in its module docstring cross-referencing the new content-pinning test, since the existing gate self-describes as structural-shape-only

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

- Confirm the structural key-parity gate still passes, and record its exact current failure signature.
- Add a prose note to the gate's module docstring cross-referencing the new content-pinning module, leaving every assertion untouched.

## Outcome

The gate stands at 332 passed and 1 failed, unchanged in both count and signature from the campaign's earlier runs. The single failure refuses a quiet run for a missing tax-residence jurisdiction scope precondition; it is pre-existing, outside this phase's surface, and was not absorbed.

The docstring note states what the gate's scope excludes rather than merely naming its sibling. The gate settles which command owns which schema and never what constraints that schema publishes, so a field retyped onto a canonical alias changes the advertised bounds without moving a single registry key and the gate stays green through it. The note directs the reader to the content pin covering both operator surfaces, and says plainly that a loosening caught by neither would be a genuine gap in the published contract.

## Notes

The module was clean against HEAD with no peer changes in flight, so a direct pathspec commit was safe and the apply-cached drive was not needed.

The diff is twelve added lines of prose and no assertion change.

A type diagnostic on this module reports an unsound return statement, and it is pre-existing: the offending line is present verbatim at HEAD, and this change touched only the module docstring.
