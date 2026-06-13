---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S297'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S297 - Close AFR-195 for file permissions

Scope: close `AFR-195` for `src/aeat/core/file_permissions.py` with signal
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited the cross-platform best-effort file-permission helper and auth session-store
  usage.
- Replaced silent POSIX `OSError` suppression with a debug log that preserves the
  non-raising hardening contract.
- Confirmed Windows `icacls.exe` execution is argv-list based and time-bounded.
- Confirmed active browser session state persists through the secure-object
  `_session_store`, not plaintext auth-state files.
- Added a source-policy test guarding against silent permission failure swallowing and
  unbounded ACL subprocesses.
- Closed `W12.P26.S297` through `vaultspec-core vault plan step check` and updated
  the `AFR-195` register status to `closed`.

## Outcome

`AFR-195` is closed. `src/aeat/core/file_permissions.py` remains a best-effort
plaintext file-permission helper, but failure paths now leave audit breadcrumbs and the
runtime auth session backend remains secure-object based.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/file_permissions.py src/aeat/core/test_file_permissions.py src/aeat/adapters/outbound/aeat/auth/_session_store.py src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/core/test_file_permissions.py src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "restrict_file_permissions Windows icacls chmod best effort warning log plaintext exception auth state token cookies" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "file permissions helper auth storage state chmod icacls bearer token session state permissions warning" --type code --port 8766 --max-results 8`

## Notes

The direct `SYSTEMROOT` and `USERDOMAIN` reads remain explicitly scoped to Windows OS
ambient context, not AEAT application configuration. The helper does not read any
AEAT-prefixed environment variable.
