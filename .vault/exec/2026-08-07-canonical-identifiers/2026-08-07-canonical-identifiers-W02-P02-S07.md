---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:926222f404439e64170078fd8c834f674ad84f622b94faf3350fce9269457825'
step_id: 'S07'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Retype every expediente_id model field onto AeatExpedienteId, removing the per-field repeated bound and the duplicated shape validator

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py`
- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_schema.py`
- `src/cadrumo/application/calculations/_iva_compensation_history.py`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part2.py`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_part3.py`
- `src/cadrumo/adapters/outbound/aeat/sede/tests/test_cotejo_csv_extraction.py`

## Description

- Retype four expediente model fields onto the shared alias across two modules.
- Delete both hand-written shape validators and the module-local compiled pattern they shared.
- Remove the now-unused `re` and `Final` imports the pattern had required.
- Fold in a fifth divergence the plan never named, on the annual-summary model.
- Correct three test fixtures carrying placeholder ids that were never AEAT-shaped.

## Outcome

Landed in `c272504f9d`. Refusal behaviour is preserved exactly: the alias carries the same window and the same pattern the deleted validators enforced.

The fifth divergence was safe to close because its sole producer is the observation field retyped in the same commit, so the tighter bound is provably satisfiable there. Leaving it would have kept a real divergence open beneath a closed checkbox.

## Notes

**Delivered wider than the row named, and the row was amended to say so.** The row scoped one file; the concept was four model fields across two modules plus the fifth divergence in a third. A row delivered wider is as much a divergence from the record as one delivered narrower, so the widening was written into the row rather than absorbed silently.

**The exception type at the boundary changed.** Moving the shape check off a hand-written validator onto a typed constraint changes what a malformed value raises, and therefore what the fault projection and the redaction funnel see. Every catcher of the adapter's own validation error was read first; all concern casilla decimal values and casilla ids, none sits on an expediente path. Five of the nine were bare catches with no message matcher, which cannot distinguish which guard fired — that class was the real exposure and had not been enumerated when the change was first proposed.

**Three fixtures refused, and all three were placeholders rather than data.** One was a redaction canary whose value was never AEAT-shaped; it keeps its distinctive marker so a leak stays detectable. The third was found only by the test run: it was bound to a module-level constant and passed as a keyword, so no literal sweep could reach it. Two independent agents had swept for the same literal pattern and both missed it — independence of agent is not independence of method.
