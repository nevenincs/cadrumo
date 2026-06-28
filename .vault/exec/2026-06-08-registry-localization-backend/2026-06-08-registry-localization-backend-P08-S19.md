---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P08.S19` execution record

Assert localized parity verification passes for newly added revision packages under `src/aeat/domain/calculations/registry/tests/test_registry_locales_parity.py`.

## Action

Updated `test_registry_locales_parity.py` to assert that:
- M100 revision `2024` casilla `"0001"` translations load.
- M200 revision `2024-y-siguientes` casilla `"00001"` translations load.
- M303 revision `2023-y-siguientes` casilla `"iva.repercutido.general"` translations load.

## Verification

Tests run sequentially and pass successfully.
