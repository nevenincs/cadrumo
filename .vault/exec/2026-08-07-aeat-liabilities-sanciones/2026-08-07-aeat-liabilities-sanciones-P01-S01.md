---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:c8bff431209492049abcbad817e5d30eb95fdf709dfacb083fe0eb56ec63772f'
step_id: 'S01'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add the closed ObjetoTributario StrEnum (interes de demora, recargo de apremio, sancion, liquidacion, other) to core, never reused or widened from PostFilingEventKind, verified by a new unit test asserting the closed member set

## Scope

- `src/cadrumo/core`

## Description

Declared the `ObjetoTributario` closed StrEnum in `core`, naming which LGT
object an AEAT-reported deuda is: an AEAT-assessed interes de demora (art.
26.2), a recargo del periodo ejecutivo (art. 28), a sancion (Titulo IV), a
liquidacion, and `OTRO` as the honest remainder for a label the axis does not
enumerate.

## Outcome

Modified files:

- `src/cadrumo/core/_objeto_tributario.py` (new)
- `src/cadrumo/core/__init__.py` (facade import plus `__all__`)
- `src/cadrumo/core/tests/test_objeto_tributario.py` (new)
- `docs/api/cadrumo.core._objeto_tributario.rst`, `docs/api/cadrumo.core.rst`
  (stubs, landed with the adapter commit below)

`OTRO` exists so an unrecognised AEAT label preserves the row rather than
being discarded or mislabelled, and the enum refuses an unknown token rather
than coercing it, keeping "AEAT said otro" distinguishable from "we did not
recognise this".

## Verification

`src/cadrumo/core/tests/test_objeto_tributario.py`, 4 tests, green. Commit
`5a0a2cd5df`, `2 0 src/cadrumo/core/__init__.py`,
`80 0 src/cadrumo/core/_objeto_tributario.py`,
`86 0 src/cadrumo/core/tests/test_objeto_tributario.py`.

## Notes

A first draft asserted the member tokens were disjoint from
`PostFilingEventKind`. That failed, and the failure was correct: `liquidacion`
is a legal noun both axes legitimately carry, one classifying the notified
event and one the resulting debt's object. Asserting disjointness would have
forced renaming a correct Spanish stem to satisfy a test, so the assertion was
replaced by the property that actually matters -- separate member IDENTITY,
plus proof the event taxonomy cannot express `recargo_apremio` or
`interes_demora` at all, which is the substantive reason the axis is its own
enum rather than added members on the existing one.

The enum was named as the plan specified.
