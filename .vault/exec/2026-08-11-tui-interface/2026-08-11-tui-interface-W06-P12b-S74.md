---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:9c23a015d17c660cf9128f78a072db35a1e8f3add2fd484a2f1c4a3b6ee81156'
step_id: 'S74'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render stable-key repeated rows with whole-row add, update, delete, and explicitly permitted move behavior, never using widget position as identity or submitting an incomplete draft row

## Scope

- `src/cadrumo/entrypoints/tui/modelo/edit/rows.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/edit/rows.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/edit/tests/test_rows_and_review.py`
- `verify:` `pytest entrypoints/tui/modelo/edit` -> `17 passed`

## Notes

Rows are addressed by the natural key the declaration already carries, never
by widget position. A position is not an identity: it changes when a row above
is removed, when a filter is applied and on every re-render, so a row edited by
position after any of those edits the WRONG row. Proven by staging two rows and
asserting both survive under their own keys.

WHOLE-ROW OPERATIONS ONLY, because a partially applied row has no meaning in a
declaration -- half a counterparty is not a smaller counterparty, it is a
malformed one. Add and replace are ONE method: whether a key is already
declared is a fact about the work unit rather than the operator's gesture, and
making the surface choose would make it guess.

NO MOVE IS OFFERED, AND THAT IS THE ROW'S 'EXPLICITLY PERMITTED' ANSWER. The
contract's intent kind documents why none exists: every row-producer sorts by a
content key before assigning fichero occurrence numbers, so two calls supplying
the same rows in different orders render byte-identical output. A move would
change nothing in the filing while implying to the operator that it had, so
this module offers none rather than one that quietly does nothing.

AN INCOMPLETE DRAFT NEVER REACHES THE SESSION. A row under construction lives
in the surface with a client correlation and no intent staged; it is committed
only when it carries BOTH its natural key and its payload. A refused commit
leaves the draft OPEN rather than dropping it, because the operator can still
see it. Committing removes it from the draft set, so a completed row cannot be
staged twice.
