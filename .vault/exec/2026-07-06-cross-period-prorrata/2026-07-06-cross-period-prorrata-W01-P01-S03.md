---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S03'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# declare the ProrrataRegister aggregate holding one entry per (ejercicio, sector) with regime and sector axes present from birth so especial and sectores land without migration (no-legacy-compatibility)

## Scope

- `src/aeat/domain/prorrata_register/__init__.py`

## Description

- Declare the strict frozen `ProrrataRegister` aggregate in `src/aeat/domain/prorrata_register/__init__.py` holding a tuple of `ProrrataRegisterEntry` rows.
- Reject a register carrying two entries for the same `(ejercicio, sector_id)` key in a model validator.
- Add the `entries_for_ejercicio`, `entry_for`, and `resolve_provisional` lookup helpers.

## Outcome

The aggregate rejects duplicate `(ejercicio, sector)` keys, lets distinct sectors of one ejercicio coexist, and resolves an entry by key. The regime and sector axes are present from birth so prorrata especial and sectores diferenciados land without migration.

## Notes

None.
