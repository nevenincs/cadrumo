---
step_id: S95
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W11.P28.S95 step record

## Step

Implement Clause 8 asserting no production module imports a `_`-prefixed name from a cross-package module other than `_ids.py`, with anti-tautology proof.

## Status

DONE

## Implementation

Fixed all 6 clause-8 private-name cross-package import violations:

Approach: promoted private names to public aliases at their definition site, then
updated cross-package callers to use the public alias instead of the private name.

- `core/parsing/_utils.py` — added `parse_bool = _parse_bool` public alias
- `core/parsing/_dates.py` — added `parse_date = _parse_date` public alias
- `core/parsing/__init__.py` — exports both `parse_bool` and `parse_date`
- `domain/fincas/_rounding.py` — added `round_to_cents = _round_to_cents` public alias

Callers updated:
- `domain/deadlines/_profiles.py` — `from aeat.core.parsing import parse_bool as _parse_bool`
  and `from aeat.core.parsing import parse_date as _parse_date_canonical`
- `adapters/outbound/aeat/sede/_censo.py` — same
- `adapters/outbound/aeat/export/_formats/_deserialise.py` —
  `from aeat.domain.fincas._rounding import round_to_cents as _round_to_cents`
- `adapters/outbound/aeat/export/_formats/_record_spec.py` — same

Zero-violation assertions for clauses 5-8 added to diagnostics test. All 21 tests pass.

## Action class

MOVE (promote private to public; update import path at call sites)

## Commits

- `f99b58dff` — exec(core-authority): W11.P28.S95 clause-8 private-name cross-package fix + zero-violation tests

## Files touched

- `src/aeat/core/parsing/_utils.py`
- `src/aeat/core/parsing/_dates.py`
- `src/aeat/core/parsing/__init__.py`
- `src/aeat/domain/fincas/_rounding.py`
- `src/aeat/domain/deadlines/_profiles.py`
- `src/aeat/adapters/outbound/aeat/sede/_censo.py`
- `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py`
- `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py`
- `src/aeat/diagnostics/test_identity_primitive_placement.py`
