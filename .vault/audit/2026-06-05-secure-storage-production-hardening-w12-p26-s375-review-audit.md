---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S375]]'
---

# `secure-storage-production-hardening` Code Review

## S375-001 | PASS | App-live CLI does not construct secure storage directly

`_app_live.py` imports application live services and payload models but does not construct `SecureObjectRepository` directly. Bucket-scoped local views resolve through the shared active-bucket helper before calling the relevant application service, keeping runtime ownership below the CLI boundary.

Evidence:
- `src/aeat/entrypoints/cli/_app_live.py:533`
- `src/aeat/entrypoints/cli/_app_live.py:1150`
- `src/aeat/entrypoints/cli/_app_live.py:1299`
- `src/aeat/entrypoints/cli/_app_live.py:1706`
- `src/aeat/entrypoints/cli/_app_live.py:1888`
- `src/aeat/entrypoints/cli/_app_live.py:2203`

## S375-002 | PASS | Settings access is centralized for watchdog and capture limits

The app-live CLI settings reads go through `load_settings()` for live IVA watchdog and capture-limit configuration. No direct environment access was found in `_app_live.py` or `_app_live_payloads.py`.

Evidence:
- `src/aeat/entrypoints/cli/_app_live.py:647`
- `src/aeat/entrypoints/cli/_app_live.py:650`
- `src/aeat/entrypoints/cli/_app_live.py:675`
- `src/aeat/entrypoints/cli/_app_live.py:677`
- `src/aeat/entrypoints/cli/_app_live.py:1949`
- `src/aeat/entrypoints/cli/_app_live.py:2006`

## S375-003 | PASS | Live IVA and read-subgroup behavior remains functional

Focused tests passed over the app-live read subgroup, filed-capture, IVA remote-state acquisition, and IVA wallet capture backend surfaces. The tests use real profile/runtime storage helpers and validate secure-object persistence through the active bucket rather than substituting storage fakes.

Commands:
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/_app_live_payloads.py src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/application/live/__init__.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_wallet_capture_backend.py`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_live_read_subgroups.py src/aeat/application/live/test_filed_bulk_capture.py src/aeat/application/live/test_iva_remote_state_acquisition.py src/aeat/application/live/test_iva_wallet_capture_backend.py`

## S375-004 | PASS | Locale drift repaired through the required CLI

The locale catalogue was audited with `python -m aeat.locales audit`. Missing live help strings and concurrent workflow resume strings were reconciled through `python -m aeat.locales set`; a stale-key removal attempt reported that the audited path was not a literal YAML leaf, and a subsequent audit reported all four locale files as ok.

Commands:
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `$env:PYTHONPATH='src'; uv run --no-sync python -m aeat.locales set ...`
- `$env:PYTHONPATH='src'; uv run --no-sync python -m aeat.locales remove ...`

## S375-005 | INFO | RAG semantic search unavailable during closure

Two `vaultspec-rag search` attempts against port 8766 timed out before returning semantic code results. The closure therefore relies on direct code inspection, focused gates, and the existing secure-storage plan/ADR chain rather than new semantic RAG evidence.

## S375-006 | PASS | Independent reviewer found no blocking issues

The `vaultspec-code-reviewer` persona reviewed the S375 app-live runtime-default closure and reported no findings. It explicitly found no HIGH or CRITICAL blockers in the scoped plan, step record, review audit, app-live CLI modules, and focused live/IVA validation tests.
