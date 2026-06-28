---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S395'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s395-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S395`

Closed `AFR-293` for the locale manager plaintext-exception slice.

## Description

- Audited `src/aeat/locales/manager.py` as the central locale YAML maintenance API.
- Verified manager exceptions derive from the AEAT base through `LocaleError`.
- Verified scan/scaffold fallbacks are logged at debug or warning level rather than silently swallowed.
- Verified locale set/remove paths are constrained to configured locale files under `locales_dir`.
- Reconciled four live locale leaves through `python -m aeat.locales set` after parity exposed filed-capture help and modelo work-address registry keys.
- Reconciled the final audit state so live `create_stub_modelo_*` refusal keys remain catalogued and the stale `relation_not_decimal` leaf is absent.
- Used vaultspec RAG semantic search to compare manager helpers with CLI and parity test coverage.
- Updated the AFR register entry for `AFR-293` to `closed`.

## Outcome

`AFR-293` is closed as `plaintext-exception`. The locale manager remains a catalogue-maintenance component with typed errors, bounded YAML-file write paths, and real-behavior test coverage for its mutation helpers.

Validation passed:

- `uv run --no-sync ruff check src/aeat/locales/manager.py src/aeat/locales/test_parity.py`
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uvx vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

No Python code change was required for this step; the locale catalog was updated through the canonical CLI so the manager parity test and `aeat.locales audit` agree.
