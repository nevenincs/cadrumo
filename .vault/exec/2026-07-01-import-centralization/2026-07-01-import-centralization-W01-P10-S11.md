---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S11'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Decide and apply the public-surface disposition for `_profile_keys` (rename-to-public and promote, expose a narrower public API, or remove the reach) currently defined in `aeat.domain.contribuyente._keys` and consumed cross-package from `src/aeat/application/user_profile/_keys_validation.py`

## Scope

- `src/aeat/domain/contribuyente/__init__.py`

## Description

- Read `_keys.py` in full: `_profile_keys()` is a private accessor returning the
  full registered `ProfileKey` tuple, raising a registration error if the
  wizard catalogue has not yet pushed the compiled keys. The module already
  exposes a public equivalent, `PROFILE_KEYS`, but only as a module attribute
  resolved through `__getattr__` (PEP 562) — which is deliberately deferred so
  the wizard catalogue can import leaf modules without triggering a premature
  build, per the existing package docstring.
- Confirmed the one consumer, `_keys_validation.py`, calls `_profile_keys()`
  (aliased `_get_profile_keys`) three times from inside function bodies, not
  at its own module-import time — it needs resolution deferred to call time,
  which a top-level `from ... import PROFILE_KEYS` binding cannot guarantee
  (it would snapshot the attribute at the consumer's import time, which can
  run before wizard-catalogue registration).
- Applied ADR Ruling 3 disposition (ii) — single narrow caller, purpose-built
  narrower public API: added a public wrapper function `profile_keys()` in
  `_keys.py` (a one-line call-through to the existing `_profile_keys()`),
  documented the distinction from the `PROFILE_KEYS` attribute, and promoted it
  through both `_keys.py`'s own `__all__` and the package
  `aeat.domain.contribuyente.__all__`. The private `_profile_keys()` function
  itself is unchanged; Wave 2 will rewire the one consumer to call
  `profile_keys()` instead.
- Ran `ruff check --fix` and `ruff format --diff` (clean), `pytest
  --collect-only -q src/aeat` (clean), `pytest -q
  src/aeat/domain/contribuyente/tests` (passed).

## Outcome

- `src/aeat/domain/contribuyente/__init__.py` and `_keys.py` both export the
  new `profile_keys()` function. Re-scanning with `dev/import_hygiene_scan.py`
  still reports `_profile_keys` as `already_in_facade: false` (expected: the
  private name itself was intentionally not renamed; the consumer still
  imports it, and Wave 2 repoints it onto `profile_keys()`).
- Committed together with the S10 promotions as `fc3e9a6ee`.

## Notes

- No incidents. This disposition adds a new symbol rather than renaming the
  existing private one, so the scanner will continue to flag
  `aeat.domain.contribuyente._profile_keys` until the Wave 2 consumer rewrite
  lands; that is expected under the applied disposition, not a gap in this
  Step.
