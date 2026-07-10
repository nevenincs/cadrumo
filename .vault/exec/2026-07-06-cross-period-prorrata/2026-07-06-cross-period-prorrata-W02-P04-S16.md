---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S16'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# wire the single declared precedence ladder into the register in-force-percentage lookup so authorised/inicio provenance outranks the carried prior definitive

## Scope

- `src/aeat/application/prorrata_register/__init__.py`

## Description

- Add `ProrrataRegisterService.resolve_provisional` as the application in-force lookup.
- Delegate candidate ordering to the domain `resolve_provisional_percentage` ladder instead of re-implementing precedence.
- Filter persisted and transient candidate entries to the requested `(ejercicio, sector)` key.
- Extend real encrypted-register service tests for authorised/inicio candidates outranking a carried entry and for sector filtering.

## Outcome

`W02.P04.S16` is implemented. The application lookup loads the persisted register entry for the requested key, accepts same-key candidate entries from seed/override resolution, and resolves the in-force percentage through the single domain ladder (`AEAT_AUTORIZADA` > `INICIO_ACTIVIDAD` > `CARRIED_PRIOR_DEFINITIVA` > unresolved).

Verification:

- `uv run --no-sync ruff check src\aeat\application\prorrata_register\__init__.py src\aeat\application\prorrata_register\tests\test_service.py`
- `uv run --no-sync pytest -q src\aeat\application\prorrata_register\tests\test_service.py src\aeat\domain\prorrata_register\tests\test_prorrata_register.py src\aeat\adapters\persistence\profile\tests\test_prorrata_register_roundtrip.py`

## Notes

No mocks, skips, xfails, new resolver convention, or new binding source kind were introduced. The later `W02.P04.S17` observation cross-check surfaces remain untouched.
