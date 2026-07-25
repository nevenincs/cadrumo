---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S230'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delegate filing import, M145 communication, workflow, and submission one-shot identifiers to core sha256_hex while preserving structured inputs, truncation, and public values

## Scope

- `src/cadrumo/application/filing/_import.py`
- `src/cadrumo/application/modelo/_m145_communication_records.py`
- `src/cadrumo/application/workflow/_models.py`
- `src/cadrumo/domain/submission/_models.py`

## Description

This Step is already satisfied at HEAD; the record documents the landed state verified against HEAD. Commit `604c8dce53` routed sixteen production one-shot SHA-256 bodies through `core.hashing.sha256_hex`, including these four modules.

- Route the filing-import submission id through `core.hashing.sha256_hex`, preserving the exact structured input and truncation.
- Route the M145 communication record's payload digest through `core.hashing.sha256_hex`, alongside the pre-existing `content_hash_hex` structured digest, unchanged.
- Route the workflow model's identifier through `core.hashing.sha256_hex`, preserving truncation.
- Route the submission domain model's identifier through `core.hashing.sha256_hex`, preserving truncation.

## Outcome

`src/cadrumo/application/filing/_import.py` imports `sha256_hex` from `...core.hashing` at line 49 and calls it at line 259 over `f"{justificante.csv}:{draft.draft_id}"`, truncating to 16 characters. `src/cadrumo/application/modelo/_m145_communication_records.py` imports both `content_hash_hex` and `sha256_hex` from `...core.hashing` at line 45; `content_hash_hex` is called at line 296 (pre-existing structured digest, untouched by this Step) and `sha256_hex` is called at line 845 for `payload_sha256`. `src/cadrumo/application/workflow/_models.py` imports `sha256_hex` at line 69 and calls it at line 509, truncating to 16 characters. `src/cadrumo/domain/submission/_models.py` imports `sha256_hex` at line 34 and calls it at line 177, truncating to 16 characters.

Verified against HEAD: all four modules' import and call sites match the audit brief exactly, and the pre-existing `content_hash_hex` structured-digest call in the M145 module is confirmed untouched (a distinct canonical helper for structured payloads, not a residual `hashlib` body).

Gate: `uv run --no-sync pytest -m "" src/cadrumo/application/filing/tests/test_import.py src/cadrumo/application/modelo/tests/test_m145_communication_create.py src/cadrumo/application/modelo/tests/test_m145_communication_export.py src/cadrumo/application/workflow/tests/test_models.py src/cadrumo/domain/submission/tests/test_repository.py src/cadrumo/domain/submission/tests/test_secure_storage_roundtrip.py` reports 52 passed.

## Notes

This record was authored after the delegation had already landed; it documents the verified state rather than performing new implementation work.
