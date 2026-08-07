---
tags:
  - '#exec'
  - '#declarations-register-pagination'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f70cec8ec7b02e7b2f5fbc578054b8f10d0c68385856a4dc5ad2c3ca97c456fb'
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

## Scope exclusion: the browser shell, deliberate and reasoned

The tests drive `_register_rows_from_snapshot`, the shared helper both walk
entry points call and the whole of their non-browser behaviour. What is NOT
exercised is the browser shell around it: the navigation to the listing URL, the
form-render check, the two combobox drives, the Buscar click and the post-Buscar
landing assertion. The row text was amended to say so rather than leaving it
claiming an end-to-end drive it does not perform.

Why the residual risk is low, stated so a reader can weigh it instead of
inferring it from silence: every excluded step PRECEDES the refusal and is
unchanged by this work. The failure mode the exclusion leaves uncovered is
therefore "walk stops reaching the helper at all", which any of the shell's own
typed navigation errors would surface loudly, not "the refusal misfires".

This exclusion is closable, and it is tracked rather than accepted permanently.
An initial reading suggested driving `walk` offline would require simulating
AEAT's ZK form, which would have been forbidden fixture engineering. That
reading was wrong: nothing in the chain has to BEHAVE like the ZK app, only be
present, visible and clickable. Route interception fulfils the real listing URL,
so the landing assertion still sees an AEAT url; the combobox drive only needs a
clickable button and visible option text; and the Buscar click needs no response
at all, because the parse reads the same document that already carries the rows.
The work is tracked as its own row rather than folded in here.
