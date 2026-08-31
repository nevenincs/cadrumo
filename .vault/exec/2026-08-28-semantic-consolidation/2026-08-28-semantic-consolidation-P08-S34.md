---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:b0a789f8f428d5a104ac55aaa70387512134ec17fd6630c3776e53c292c46d1c'
step_id: 'S34'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Declare the source-locator bound once: the same concept carries no bound, 512 and 1024 at different sites

## Scope

- `src/cadrumo/`

## Changes

- `A` `src/cadrumo/core/source_locator.py`
- `M` `src/cadrumo/application/live/deudas.py`
- `M` `src/cadrumo/application/overview/calendar_models.py`
- `verify:` alias probed at lengths 1, 512, 600, 1024, 1025 -- refuses only above 1024
- `verify:` `pytest overview + live -k "calendar or deudas" -n 0 -m ""` -> 163 pass, 8 unrelated

## Notes

The step names three strengths for one concept and the census found the name
carrying THIRTEEN distinct annotations. Most are different concepts wearing a
similar name -- a registry citation, a parsed AnyHttpUrl, a filesystem path --
and the census's job was separating those from the one real disagreement.

It is the capture and its projection. `application/live/deudas.py` persists a
snapshot whose `source_url` sets a minimum and NO maximum; the overview calendar
entry copies that value straight across at `calendar.py:396` into a field capped
at 512. A persisted URL longer than the cap does not truncate, it refuses -- and
it refuses the whole calendar entry, so one long sede link would take out the
overview for that taxpayer rather than that one field.

The bound is the generous one deliberately. A sede URL carries session and
procedure parameters and is long by nature, so tightening the persisted side to
512 would refuse links the portal really issues; 1024 is what this codebase
already gives a stored URL on its ORM column. The corpus fetch record and that
column already agree on 1024 and were left alone -- they are a different concept
and they already agree with each other.

`OptionalSourceUrl` is separate rather than `SourceUrl | None` because the
projection spells an absent value as the empty string on the wire, and a minimum
of one would refuse it.
