---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S228'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate storage rotation, SQL engine, and calculation-sheet one-shot identifiers to core sha256_hex while preserving exact payload construction and truncation

## Scope

- `src/cadrumo/adapters/persistence/storage/_rotation.py`
- `src/cadrumo/adapters/persistence/storage/sql/engine.py`
- `src/cadrumo/application/storage/calc_sheets/_engine.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` routed sixteen production one-shot SHA-256 bodies through `core.hashing.sha256_hex`, including these three modules.

- Route the storage rotation route marker through `core.hashing.sha256_hex`, preserving the exact encoded path and its truncation.
- Route the SQL engine route marker through `core.hashing.sha256_hex`, preserving the exact encoded URL and its truncation.
- Route the calc-sheet registry stamp through `core.hashing.sha256_hex`, preserving the exact canonical payload and its truncation.

## Outcome

`src/cadrumo/adapters/persistence/storage/_rotation.py` imports `sha256_hex` from `....core.hashing` at line 40 and calls it at line 67, truncating to 16 characters. `src/cadrumo/adapters/persistence/storage/sql/engine.py` imports `sha256_hex` from `.....core.hashing` at line 42 and calls it at line 64, truncating to 16 characters. `src/cadrumo/application/storage/calc_sheets/_engine.py` imports `sha256_hex` from `....core.hashing` at line 22 and calls it at line 109, truncating to 16 characters.

Verified against HEAD: all three modules' import and call sites match the audit brief exactly and preserve their respective encodings and truncations.

Gate: `uv run --no-sync pytest -m "" src/cadrumo/adapters/persistence/storage/tests/test_rotation.py src/cadrumo/adapters/persistence/storage/sql/tests/test_engine.py src/cadrumo/application/storage/calc_sheets/tests/test_engine_hardening.py` reports 37 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
