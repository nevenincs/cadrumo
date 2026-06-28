---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P04.S10` execution record

Add dedicated `test_registry_locales_parity.py` and verify end-to-end integration.

## Action

1. Created `src/aeat/domain/calculations/registry/tests/test_registry_locales_parity.py` which compiles the entire registry tree and verifies that all defined translation keys point to valid continuity IDs or casilla IDs (referential integrity).
2. Created `src/aeat/entrypoints/cli/tests/test_registry_locales_cli.py` to verify the end-to-end CLI integration, verifying default Spanish output, `--language` flag overrides, `--explain` helper columns, and JSON envelope output format.
3. Verified the implementation against all other registry tests and the integration suite.

## Verification

Run all locales tests sequentially:
- `pytest src/aeat/domain/calculations/registry/tests/test_registry_locales_parity.py`
- `pytest src/aeat/entrypoints/cli/tests/test_registry_locales_cli.py -m integration`
Both run and pass cleanly.
