---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S297-001 | FIXED | POSIX chmod failures were silently swallowed

`src/aeat/core/file_permissions.py` previously used `contextlib.suppress(OSError)` for
the POSIX `chmod(0o600)` branch. That made a best-effort failure invisible. The branch
now catches `OSError` and logs a debug breadcrumb with `exc_info=True`, preserving the
non-raising hardening contract while satisfying the no-silent-swallow rule.

Disposition: close `AFR-195` after the debug breadcrumb fix.

## S297-002 | PASS | Windows ACL subprocess is bounded and non-shell

The Windows branch invokes `icacls.exe` with an argv list, `shell=False` by omission,
`check=False`, captured output, and the `_ICACLS_TIMEOUT_SECONDS` timeout. All
Windows hardening failures remain warning-logged and non-fatal because auth-state
permission tightening is a side effect, not the persistence authority.

## S297-003 | PASS | Active auth session persistence uses secure objects

RAG and focused inspection showed current browser session persistence flows through
`src/aeat/adapters/outbound/aeat/auth/_session_store.py`, which saves the Playwright
storage state at `SESSION` sensitivity via `SecureObjectRepository`. The file-permission
helper remains a compatibility/public hardening helper and is not the active session
secret persistence backend.

## S297-004 | PASS | Guard test covers safety policy without mocks

Added `src/aeat/core/test_file_permissions.py` to parse the real helper source and
guard against reintroducing `contextlib.suppress` around permission failures or an
unbounded `subprocess.run` call. The secure session-store roundtrip test continues to
exercise the real encrypted runtime repository path.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/file_permissions.py src/aeat/core/test_file_permissions.py src/aeat/adapters/outbound/aeat/auth/_session_store.py src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/core/test_file_permissions.py src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "restrict_file_permissions Windows icacls chmod best effort warning log plaintext exception auth state token cookies" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "file permissions helper auth storage state chmod icacls bearer token session state permissions warning" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
