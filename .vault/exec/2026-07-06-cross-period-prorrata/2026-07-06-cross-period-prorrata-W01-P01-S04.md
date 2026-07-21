---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# implement the pure precedence-ladder resolver (authorised/inicio provenance > carried prior definitive > no value) returning the in-force provisional percentage or None, never a fabricated default, with unit tests over the ladder

## Scope

- `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py`

## Description

- Implement the pure LIVA art. 105 precedence-ladder resolver `resolve_provisional_percentage` in `src/aeat/domain/prorrata_register/__init__.py`, returning a typed `ProrrataProvisionalResolution`.
- Rank provenances by the single declared ladder (`AEAT_AUTORIZADA` > `INICIO_ACTIVIDAD` > `CARRIED_PRIOR_DEFINITIVA`); ignore candidates that carry no provisional percentage; resolve absence to a visible unresolved state (both fields `None`), never a fabricated default.
- Add the unit-test suite in `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py` covering the ladder tiers, the tie-break, the unresolved case, the entry-coupling invariants, and the aggregate lookups.

## Outcome

18 unit tests pass (`-n0`). The ladder returns the highest-precedence provenance's percentage; the no-candidate and regime-only cases resolve to `None`, proving the "no fabricated 100%" invariant. `ruff` / `ruff format` / `ty` clean; `domain-not-application` import contract KEPT (the domain register imports only `core`).

## Notes

Validator errors raised inside pydantic surface as `pydantic.ValidationError` (the custom `ProrrataRegisterValidationError` is a `ValueError` subclass pydantic wraps), so the tests assert `pydantic.ValidationError` with a message match, mirroring the `bienes_inversion` roundtrip convention.
