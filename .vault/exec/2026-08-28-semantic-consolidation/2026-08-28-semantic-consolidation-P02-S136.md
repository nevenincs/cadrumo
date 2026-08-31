---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5d20473aadca124a34d5135a48822f10723fb95b94deaa70f68b1754e3dee20f'
step_id: 'S136'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the calendar-month bound and its predicate once and adopt them at eight sites, two of which stated the same field's rule twice in one module

## Scope

- `src/cadrumo/core/text_bounds.py`
- `src/cadrumo/domain/contribuyente/`
- `src/cadrumo/application/wizard/`
- `src/cadrumo/entrypoints/cli/`

## Changes

- `M` `src/cadrumo/core/text_bounds.py`
- `M` `src/cadrumo/domain/contribuyente/descendant_record.py`
- `M` `src/cadrumo/domain/contribuyente/descendant_facts.py`
- `M` `src/cadrumo/domain/contribuyente/family_types.py`
- `M` `src/cadrumo/application/wizard/descendant_group.py`
- `M` `src/cadrumo/entrypoints/cli/_config_descendiente_payloads.py`
- `verify:` is_calendar_month probed at 0, 1, 12, 13
- `verify:` `pytest src/cadrumo/domain/contribuyente src/cadrumo/application/wizard -n 0 -m ""` -> 835 pass, 4 unrelated fail

## Notes

Reported as four sites. There are eight, and the two the report missed are the
ones worth having: alta_posterior_nacimiento_mes has its month rule stated TWICE
inside descendant_facts.py -- once reading the profile answer store, once parsing
a flag string -- plus a third time as a Field bound on the record. The CLI
payload module the report called an adopter of the alias hand-rolls the loop as
well, so it does both.

Two aliases would not have been enough, because five of the eight cannot use an
annotation at all: each raises its OWN refusal, and they differ on purpose --
ProfileAnswerTypeError naming the answer key, ProfileValidationError, a failed
wizard verdict carrying a locale key, a plain ValueError pydantic wraps. What is
shared is the question, so is_calendar_month sits beside CalendarMonth the way
is_unit_proportion sits beside UnitProportion.

_filing_projection_ref.py declares a slot with the same 1-12 bound and is
deliberately left alone: a slot is a numbered group-company row on the M200 INCN
sheet, which happens to top out at twelve. Same numbers, different fact.
