---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S364'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S364 - Close AFR-262 for submission protocols

Scope: close `AFR-262` for `src/aeat/domain/submission/_protocols.py` with signals
`plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `_protocols.py` for direct secure-storage access, active-profile resolution,
  settings/environment access, filesystem IO, and remote-provider client calls.
- Confirmed the module declares strict pydantic records and runtime-checkable
  protocols only; it does not execute provider, storage, or filesystem behavior.
- Confirmed the `Path` import is type-surface only for `ModeloDraftLoader.load`, and
  the unused-name-safe `_draft_path` parameter remains intentional protocol shape.
- Confirmed the remote-provider signal is provenance from protocol names such as
  `AuthProviderProbe` and `DeadlineWindowChecker`, not a direct remote mirror writer.
- Closed `W12.P26.S364` through `vaultspec-core vault plan step check` and updated
  the `AFR-262` register status to `closed`.

## Outcome

`AFR-262` is closed. `_protocols.py` is a pure structural contract module for the
submission engine and does not own plaintext state, secure storage, active buckets,
settings, environment variables, or remote-provider IO.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/submission/_protocols.py src/aeat/domain/submission/_preflight.py src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py src/aeat/adapters/outbound/aeat/export/tests/test_errors.py src/aeat/adapters/outbound/aeat/export/tests/test_engine.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py src/aeat/adapters/outbound/aeat/export/tests/test_errors.py src/aeat/adapters/outbound/aeat/export/tests/test_engine.py -k "preflight or error"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

`vaultspec-rag search` timed out on port 8766 while researching this slice, so the
closeout relies on direct source inspection, focused gates, and the existing
secure-storage plan and ADR chain.
