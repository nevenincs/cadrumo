---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S550
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P36.S550`

S550 regression fix: deleted the duplicate `canonical_decimal` implementation in `_decimal.py` and migrated all callers within `aeat.adapters.inbound.financial` to import `canonical_decimal_string` from `aeat.domain._identifiers`.

- Deleted: `src/aeat/adapters/inbound/financial/_decimal.py`
- Modified: `src/aeat/adapters/inbound/financial/__init__.py`
- Modified: `src/aeat/adapters/inbound/financial/test_decimal.py`

## Description

`_decimal.py` defined `canonical_decimal` with identical logic to `canonical_decimal_string` in `aeat.domain._identifiers`. The domain location is the canonical home per the hexagonal architecture rule (deeper layer). The duplicate was deleted in full per the `retire_means_delete_fully` memory rule — no shim, no alias, no deprecation marker.

`__init__.py` now imports `canonical_decimal_string` from `aeat.domain._identifiers` and re-exports it under the alias `canonical_decimal` to preserve the public surface of the financial package. `test_decimal.py` migrated its import to use the same domain path. No provider files required changes (none imported `canonical_decimal` directly).

Caller migration count: 2 files (`__init__.py`, `test_decimal.py`). The `canonical_decimal` name in `__init__.py.__all__` is preserved as a re-export alias; no external consumer needed updating.

## Tests

Grep post-condition confirms exactly 1 definition of `canonical_decimal_string` across `src/aeat/`. All 4 `test_decimal.py` tests pass against the domain implementation.
