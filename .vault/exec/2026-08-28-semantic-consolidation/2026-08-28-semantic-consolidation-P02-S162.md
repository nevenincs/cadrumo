---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:471116a8fc3b3f37c5bd34f9c103dcdd70e462445c75d15669f306387fcdb36e'
step_id: 'S162'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# State the canonical month-set rule once, so the descendant record and the wire payload projecting it stop implementing uniqueness and ordering separately

## Scope

- `src/cadrumo/core/text_bounds.py`
- `src/cadrumo/domain/contribuyente/descendant_record.py`
- `src/cadrumo/entrypoints/cli/_config_descendiente_payloads.py`

## Changes

- `M` `src/cadrumo/core/text_bounds.py`
- `M` `src/cadrumo/domain/contribuyente/descendant_record.py`
- `M` `src/cadrumo/entrypoints/cli/_config_descendiente_payloads.py`
- `verify:` predicate probed at (1,2,3), (1,1,2), (3,2,1), (0,1), (13,), ()
- `verify:` `pytest domain/contribuyente -k "descendant or meses" -n 0 -m ""` -> pass (184)
- `verify:` `pytest descendiente payload parity + payload gate -n 0 -m ""` -> pass (31)

## Notes

The wire validator's docstring says it "mirrors the canonical month-set rules",
and a mirror should ASK the rule rather than re-derive it. Only the first of the
three delegated -- `is_calendar_month`, adopted in an earlier step -- while
uniqueness and ascending order were written out on both sides.

`is_canonical_month_set` now states all three once. A predicate rather than a
shared validator because the two callers raise different errors deliberately:
the record a `ProfileValidationError` naming the repeated months for an operator
who typed them, the payload a plain `ValueError` saying only that the set is
malformed. The record therefore asks the predicate first and builds its detailed
refusal only on failure -- the rule is one question, and what follows it is
message-building.

The empty tuple is canonical, which the probe confirms rather than assumes: a
descendant with no qualifying months is a normal record, not a malformed one.

P02.S05 is marked with this, and its remaining surface is named honestly rather
than swept in: `_overview_payloads.py` still carries four coherence validators --
a justificante-CSV requirement, an inclusive date order, a single-profile
coverage rule. Those are cross-field rules about one payload's internal
consistency, not restatements of a canonical bound, so they are not this step's
kind of finding and were not forced into it.
