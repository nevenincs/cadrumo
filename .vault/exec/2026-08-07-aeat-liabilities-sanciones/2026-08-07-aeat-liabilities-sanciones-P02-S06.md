---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:495511c4cf5a58c84c57afdc574b15edd6374943d3140a06c085fd2b889ff914'
step_id: 'S06'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add DeudasService extending StatelessSnapshotService with capture, list_snapshots, show and latest verbs, structurally read-only by construction with no method that mutates AEAT state

## Scope

- `src/cadrumo/application/live/_deudas.py`

## Description

Added `DeudasService` extending `StatelessSnapshotService`, with `capture`,
`list_snapshots`, `show` and `latest`.

## Outcome

Modified files:

- `src/cadrumo/application/live/_deudas.py`

Read-only by construction, and more strictly than the expedientes sibling: no
fetch path exists at all. There is no specimen of AEAT's consulta page and the
adapter guard refuses every landing, so the service persists and reads only
what a future authorised capture would supply. The docstring states the
absence is deliberate rather than unfinished.

## Verification

`test_deudas_service.py`, 8 tests, green, covering dedup on identical
re-capture, distinct ids for a different reading, `latest` resolving by capture
time, and `latest`/`list_snapshots` reporting empty rather than reaching for
AEAT. Commit `685abbf6b4`.

## Notes

Added a structural assertion over the public surface rather than trusting the
current file contents: no public method name may contain a paying, filing,
acknowledging or aplazamiento verb. On a payment-adjacent surface that is a
property worth gating, because a later contributor adding a convenience verb
would otherwise pass every existing test.
