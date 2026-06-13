---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S107'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-005 for OFX financial provider

## Scope

- `src/aeat/adapters/inbound/financial/providers/_ofx.py`
- `src/aeat/adapters/inbound/financial/providers/test_ofx.py`

## Description

- Classify `OfxProvider` as a `plaintext-exception` inbound financial-source parser.
- Confirm the provider reads caller-supplied OFX/QFX files and yields in-memory `RawTransaction` records without constructing secure-storage repositories or persisting local side-store data.
- Replace source filename/path diagnostics with the stable `<input-ofx>` placeholder.
- Replace validation dialect account identifiers with an `account_count` summary.
- Add real-behavior tests for invalid-source filename redaction and account-id suppression in validation diagnostics.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/inbound/financial/providers/_ofx.py src/aeat/adapters/inbound/financial/providers/test_ofx.py` passed.
- `uv run pytest -q src/aeat/adapters/inbound/financial/providers/test_ofx.py` passed: 3 passed, with third-party `ofxparse` deprecation warnings.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md S107` closed the row.

## Notes

- `RawTransaction.provenance.source_path` still carries the resolved source path through the shared financial provider base. This is broader than the OFX provider and remains a secure-storage enrollment follow-up for persisted financial observations.
