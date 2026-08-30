---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6256025f95272d3084ed6a9f633bf59d36191736745da1d594f4892fa71d5a5a'
step_id: 'S37'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Generate the current-HEAD action-denominator artifact with every C1 direct query classified, modelo.work.create DEFERRED under work-lifecycle ownership, modelo.work.amend a distinct future C4 mutation, and modelo.work.amend_wizard FLOW_OWNED pending C4 disposition

## Scope

- `.vault/reference/2026-08-24-tui-modelo-workspace-action-denominator.md`

## Changes

- `A` `.vault/reference/2026-08-24-tui-modelo-workspace-action-denominator-reference.md`
- `verify:` `validate_modelo_workspace_action_denominator(build_modelo_workspace_action_denominator())` -> `[]` (78 rows, zero violations)

## Notes

Filename carries the `-reference` suffix the scaffolding CLI produces for this
document type (matching the precedent already established by
`2026-08-24-tui-operation-observation-dependency-receipt-reference.md`); the
plan row's cited path omits it. The digest pinned in this artefact
(`rows_digest`) covers ONLY the 78 classification rows themselves, never a
tree-wide scalar, so an unrelated peer commit elsewhere cannot flap it. The
`disposition_tally` field is descriptive provenance, not a pinned pass
condition — no test asserts an exact count against it.

CORRECTION 2026-08-30: the `.vault/reference/` artefact listed above no longer
exists. Commit `280ec80a67` deleted it on 2026-08-28 under a subject announcing
only additive work for the semantic-consolidation feature. The deletion is
defensible -- the document was a SNAPSHOT of generated data, reproducible by
calling `build_modelo_workspace_action_denominator()` -- so no information was
lost, but this record must not keep asserting a file that is gone.

The row's substance is satisfied and was re-measured at HEAD rather than taken
from this record: `dev/quality/modelo_workspace_action_denominator.py` exists,
both public functions resolve, the validator returns ZERO violations, and
`dev/tests/test_modelo_workspace_action_denominator.py` holds it as a standing
gate at 9 passing tests.

- `verify:` `validate_modelo_workspace_action_denominator(build_...())` -> `0 violations`
- `verify:` `pytest dev/tests/test_modelo_workspace_action_denominator.py` -> `9 passed`

This row is NOT of the same kind as W01.P01.S01 and W05.P10.S38, whose C1
receipt subject commit `51023bdad2` retired outright. That commit explicitly
preserved the action denominator, so the three rows must not be swept together.
