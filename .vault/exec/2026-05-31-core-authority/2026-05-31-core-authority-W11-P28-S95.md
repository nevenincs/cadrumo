---
step_id: S95
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S95 step record

## Step

Implement Clause 8 asserting no production module imports a `_`-prefixed name from a cross-package module other than `_ids.py`, with anti-tautology proof.

## Status

BLOCKED

## Implementation

Added `find_private_name_cross_package_imports()` to `src/aeat/diagnostics/_identity_placement.py`.
Detector excludes test files (`test_*.py`), files in `tests/` directories, dunder names
(`__version__` etc.), relative imports (within-package), `_ids.py` modules (covered by clause 2),
modules on the protect list, and same-package imports.
Anti-tautology proof `test_private_name_cross_package_detector_flags_synthetic_violation` added.

## Blocked reason

6 production violations remain:

- `src/aeat/domain/deadlines/_profiles.py:17,18` — `_parse_bool`, `_parse_date` from
  `aeat.core.parsing`. Owning wave: W09/W10 (core outbound / import-direction purge).
- `src/aeat/adapters/outbound/aeat/sede/_censo.py:36,37` — same private functions.
  Owning wave: W09/W10.
- `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py:26` — `_round_to_cents`
  from `aeat.domain.fincas._rounding`. Owning wave: W09/W10.
- `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py:33` — same.

## Commit

`8a08cac3f` — diagnostics(W11.P28): extend enforcement test to 10 clauses per Rule 11

## Files touched

- `src/aeat/diagnostics/_identity_placement.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py`
