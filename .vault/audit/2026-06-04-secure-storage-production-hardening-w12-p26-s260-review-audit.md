---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S260]]'
---

# `secure-storage-production-hardening` `W12.P26.S260` Review

## S260-001 | HIGH | Translator errors rendered raw formula identifiers

Multiple translator failure paths interpolated registry ops, parameter ids, or layout identifiers directly into `TranslationError` messages. The translator can be reached through registry-backed workbook export and parity workflows, so those diagnostics must not leak arbitrary formula-surface tokens. `TranslationError` now always renders a stable message, carries a locale key, and exposes only bounded structured context.

## S260-002 | PASS | Translation boundary remains remote-mirror only

The translator remains a pure closed-form compiler from registry expressions to A1 formula fragments. It does not persist data, read environment variables, emit logs, write local files, or call remote APIs. It remains classified as `remote-mirror` because its output is later sent to Google Sheets by the outbound apply adapter.

## S260-003 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/storage/calc_sheets/_translator.py src/aeat/application/storage/calc_sheets/test_translator_hardening.py src/aeat/application/storage/calc_sheets/test_layout_hardening.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/storage/calc_sheets/test_translator_hardening.py src/aeat/application/storage/calc_sheets/test_layout_hardening.py src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py src/aeat/application/storage/calc_sheets/test_modelo_export_formatting.py src/aeat/adapters/outbound/google/test_calc_sheets_export_integration.py` passed with 32 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-158` as `remote-mirror` with translator failure localization and redaction hardened.
