---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S14'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add the aeat_autorizada override entry recording the art-105.Dos AEAT-authorised provisional percentage plus its authorisation reference

## Scope

- `src/aeat/application/prorrata_register/__init__.py`

## Description

- Add `ProrrataRegisterService.record_aeat_autorizada` to build and persist an art. 105.Dos authorised provisional entry.
- Stamp the entry with `AEAT_AUTORIZADA`, the caller's authorisation reference, optional sector id, and declared regime.
- Cover the service through real encrypted-register repository tests, including replacement of an existing carried entry and sector/regime preservation.

## Outcome

`W02.P04.S14` is implemented. The application facade can now record an AEAT-authorised provisional prorrata override without adding a parallel write path: it constructs the strict `ProrrataRegisterEntry` and delegates to the existing `declare`/repository upsert flow.

Verification:

- `uv run --no-sync ruff check src\aeat\application\prorrata_register\__init__.py src\aeat\application\prorrata_register\tests\test_service.py`
- `uv run --no-sync pytest -q src\aeat\application\prorrata_register\tests\test_service.py src\aeat\domain\prorrata_register\tests\test_prorrata_register.py src\aeat\adapters\persistence\profile\tests\test_prorrata_register_roundtrip.py`

## Notes

No mocks, skips, xfails, new resolver convention, or new binding source kind were introduced. The later `W02.P04.S16` precedence wiring remains untouched.
