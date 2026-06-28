---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-application-ledger-fixture-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` Application Ledger Fixture Slice

## Description

- Remove redundant fixture-level `dispose_engine()` wrappers from application ledger tests already using `isolated_runtime_profile`.
- Preserve real secure-object repositories, transaction catalogues, bucket event history, invoice evidence, work-unit repositories, and CLI-independent application service execution.
- Keep the slice limited to clean application ledger fixtures and away from explicit route-classification/refusal tests.

## Changed Surface

- `src/aeat/application/ledger/test_actions.py`
- `src/aeat/application/ledger/test_merge.py`
- `src/aeat/application/ledger/test_preflight.py`
- `src/aeat/application/ledger/test_split.py`

## Outcome

Closed for this slice.

The four ledger fixtures now rely on the centralized runtime-profile helper for settings-bound engine setup and teardown instead of wrapping it in local disposal boilerplate. The tests still exercise real encrypted repositories and persisted ledger behavior.

## Verification

- `uv run --no-sync pytest -q src/aeat/application/ledger/test_split.py src/aeat/application/ledger/test_preflight.py src/aeat/application/ledger/test_merge.py src/aeat/application/ledger/test_actions.py` - 101 passed.
- `uv run --no-sync ruff check src/aeat/application/ledger/test_split.py src/aeat/application/ledger/test_preflight.py src/aeat/application/ledger/test_merge.py src/aeat/application/ledger/test_actions.py` - all checks passed.
- `rg -n "aeat_database_url|AEAT_DATABASE_URL|SecretStoreBackend|dev_test_database_password|dispose_engine\\(|monkeypatch|pytest\\.mark\\.skip|pytest\\.mark\\.xfail|_Fake|_Stub" src/aeat/application/ledger/test_split.py src/aeat/application/ledger/test_preflight.py src/aeat/application/ledger/test_merge.py src/aeat/application/ledger/test_actions.py` - no matches.
- `git diff --check -- src/aeat/application/ledger/test_split.py src/aeat/application/ledger/test_preflight.py src/aeat/application/ledger/test_merge.py src/aeat/application/ledger/test_actions.py` - no whitespace errors.

## Notes

S93 remains open because the row covers broader `src/aeat` explicit-route and injected-engine setup. Remaining work includes approved-route classification, repair privacy diagnostics follow-up, manual bucket-session tests, `test_modelo_export_verb.py`, profile lifecycle fixture cleanup, and guard/closeout rows S94-S95.
