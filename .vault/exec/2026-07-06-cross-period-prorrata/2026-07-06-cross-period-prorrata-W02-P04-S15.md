---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S15'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add the inicio_actividad override entry recording the art-105.Tres (via art-111.Dos) inicio-de-actividades proposed percentage plus its reference

## Scope

- `src/aeat/application/prorrata_register/__init__.py`

## Description

- Add `ProrrataRegisterService.record_inicio_actividad` to build and persist an art. 105.Tres inicio-de-actividades proposed provisional entry.
- Stamp the entry with `INICIO_ACTIVIDAD`, the caller's proposal reference, optional sector id, and declared regime.
- Extend the real encrypted-register service tests to cover replacement of an existing carried entry and sector/regime preservation for inicio records.

## Outcome

`W02.P04.S15` is implemented. The application facade can now record an inicio-de-actividades proposed provisional prorrata override through the same strict entry construction and repository upsert path as the rest of the register service.

Verification:

- `uv run --no-sync ruff check src\aeat\application\prorrata_register\__init__.py src\aeat\application\prorrata_register\tests\test_service.py`
- `uv run --no-sync pytest -q src\aeat\application\prorrata_register\tests\test_service.py src\aeat\domain\prorrata_register\tests\test_prorrata_register.py src\aeat\adapters\persistence\profile\tests\test_prorrata_register_roundtrip.py`

## Notes

No mocks, skips, xfails, new resolver convention, or new binding source kind were introduced. The later `W02.P04.S16` precedence wiring remains untouched.
