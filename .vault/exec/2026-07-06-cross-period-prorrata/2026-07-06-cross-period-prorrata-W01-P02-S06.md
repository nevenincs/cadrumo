---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-08'
step_id: 'S06'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# implement the encrypted ProrrataRegisterRepository (governed singleton save/load through SecureObjectRepository) on the bienes_inversion adapter pattern

## Scope

- `src/aeat/adapters/persistence/profile/prorrata_register.py`

## Description

- Implement the encrypted `ProrrataRegisterRepository` in `src/aeat/adapters/persistence/profile/prorrata_register.py` on the `bienes_inversion` adapter pattern: governed singleton `load`/`save` through `SecureObjectRepository`, FINANCIAL-class ciphertext, empty register when the envelope is absent.
- Add `upsert_entry` (add-or-replace by `(ejercicio, sector_id)` key) plus the module-level `load_prorrata_register` / `save_prorrata_register` / `declare_prorrata_entry` convenience functions.
- Raise `ProrrataRegisterError` on a decrypt/load failure.

## Outcome

The repository round-trips the encrypted register through real SQLite; `upsert_entry` replaces an existing key in place (the ejercicio entry's provisional→settled lifecycle). `ruff` / `ruff format` / `ty` clean.

## Notes

Chose add-or-replace `upsert` semantics over the `bienes_inversion` refuse-duplicate `add`, because one `(ejercicio, sector)` entry is updated across its lifecycle (provisional seed, then definitive settlement) rather than being a distinct-identifier ledger row. The `translated_message` override was dropped from the load-failure error (the registered ErrorCode already carries the message) to avoid a locale scaffold pass that would have swept unrelated peer keys into this change.
