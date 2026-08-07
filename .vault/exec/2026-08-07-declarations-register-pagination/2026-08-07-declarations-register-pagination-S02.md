---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:46f5e2c5c464696ba9d974fb38f0f30245da6d79c9d2997c1073d7e93fc8ebd1'
step_id: 'S02'
related:
  - "[[2026-08-07-declarations-register-pagination-plan]]"
---
## Description

Both register-walk entry points drove one search-then-parse cycle and returned
whatever rendered. With the declared total now available, a page short of its own
declared size is refused instead of returned.

## Outcome

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations.py` gains
  `_register_rows_from_snapshot`, which parses one snapshot and raises
  `SedeParseError` when the page reports itself truncated, naming the modelo,
  ejercicio, rendered count and declared total in both the message and the
  error context.
- `DeclaracionesRegisterSession.walk` and `walk_declarations_register` each call
  it in place of the bare parse. One shared helper rather than a check duplicated
  per entry point, so the two paths cannot drift apart, and both docstrings now
  declare the refusal.

## Verification

Focused run of the sede declarations tests plus the live bulk-capture module:
26 passed. `ruff`, `ruff format --check` and `ty check` clean.

## Notes

The refusal message is deliberately short and fact-first. The bulk sweep bounds
a failure row's message at 160 characters, and the first wording overran it — the
counts survived but the reason was cut off mid-word. That was caught by a real
run, not by inspection, and the length constraint is now asserted.

No `SedeFailureMode` member describes a truncated result, and adding one is wider
than this decision authorises, so the refusal carries the default mode and puts
its detail in `context`. No locale key was added: the four catalogues carry peer
work in flight and this surface needed no new operator string.

Read honestly against the row's gate: the tests drive
`_register_rows_from_snapshot`, which is the entire non-browser behaviour of both
walk entry points and the exact function each calls, rather than `walk` itself.
Driving `walk` needs a Playwright page against the live Sede, which no
authorisation covers. What is not exercised is the browser shell around the
parse — the navigation, the Buscar click and the landing assertion, all of which
precede the refusal and are unchanged by it.
