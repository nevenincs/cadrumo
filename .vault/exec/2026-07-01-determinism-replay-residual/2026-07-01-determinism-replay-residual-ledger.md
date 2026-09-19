---
tags:
  - '#exec'
  - '#determinism-replay-residual'
date: '2026-07-01'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:eb0717010fec6b2870c52b2ed7ca0b63eb67b9b588c5ab4ed60a637c6fd56af2'
related:
  - "[[2026-07-01-determinism-replay-residual-plan]]"
---

# `determinism-replay-residual` ledger

## Changes

- `S01` `T` `route corpus_manifest generated_at through core.time.now().`
- `S01` `T` `src/aeat/core/tests/test_clock_seam_usage.py`
- `S01` `T` `src/aeat/core/corpus_manifest/__init__.py`
- `S02` `T` `add roundtrip + anti-tautology proofs`
- `S02` `T` `add a ledger-evidence --format json golden scenario under frozen_clock with injected profile_id`
- `S02` `T` `adding a residual mask entry only if an opaque single-command leaf remains.`
- `S02` `T` `src/aeat/application/ledger/_evidence.py`
- `S02` `T` `src/aeat/application/ledger/_business_operation_invoice.py`
- `S02` `T` `src/aeat/core/observability/_golden.py`
- `S03` `T` `wrap the output-feeding scans in sorted() at the boundary and leave the membership/aggregation scans alone.`
- `S03` `T` `src/aeat/application/user_profile/_profile_repository.py`
- `S03` `T` `src/aeat/entrypoints/cli/_ledger_import_cli.py`
- `S04` `T` `enrol the ledger-add retried-no-op as the first state-transition case asserting db_sha256 identity after the idempotent second add against a hermetic synthetic var root.`
- `S04` `T` `src/aeat/core/observability/tests/test_determinism_conformance.py`
