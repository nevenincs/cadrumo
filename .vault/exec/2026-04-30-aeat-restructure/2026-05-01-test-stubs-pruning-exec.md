---
tags:
  - '#exec'
  - '#aeat-restructure'
date: '2026-05-01'
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-summary-exec]]"
---

# `aeat-restructure` `test-pruning` `eliminate-shims-colocated-tests`

Pruned stub/fake/spy patterns from colocated test files under `src/aeat/`.

- Modified: `src/aeat/adapters/outbound/aeat/browser/test_session.py`
- Modified: `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py`

## Description

Two targeted changes applied per the eliminate-shims mandate:

**`test_session.py`** — `DummyEvasion` had `self.called = True/False` spy tracking
and `test_browser_session_creation` asserted `evasion.called`. The spy fields were
removed; the class is now a pure no-op concrete `EvasionStrategy` implementation.
The `assert evasion.called` assertion was deleted. The class itself is kept because
real Playwright cannot run headlessly in unit tests — it is a legitimate 3rd-party
boundary stub, not a counter-based mock.

**`test_authenticator.py`** — `test_describe_forwards_bundle_backend_and_friendly_name`
patched `certificate_health` inside `src/aeat/` via `monkeypatch.setattr` on the
module reference to capture call arguments (spy pattern). The real function was
still called but the test's purpose was to verify argument forwarding via side-effect
capture. This is a shadow test — patching what it claims to verify. The test and its
now-unused `authenticator_module` import were deleted.

All other `monkeypatch.setattr` calls reviewed and confirmed clean:
- `keyring.*` patches — legitimate 3rd-party boundary isolation (KEEP)
- `PROJECT_ROOT` / `EXPECTED_COUNTS` / `SANITIZED_SHAS` patches — env-var-like
  constant overrides (KEEP)
- `os.replace` patches in `_test_master_key.py` — stdlib failure simulation (KEEP)
- `TransactionCatalogueRepository.save` patches — rollback error-path testing of a
  *different* function (`link_transaction_bidirectional`), not a shadow test (KEEP)
- `Settings` subclass patches in `test_auth_cli.py` — redirect env-file I/O to
  tmp_path for isolation (KEEP)

No `@patch` decorators, `unittest.mock` imports, or unused Fake/Stub/Dummy class
definitions found across all files in scope.

## Tests

Collection baseline: 65 errors, 6120/6129 tests collected.
Collection after changes: 67 errors, 6142/6153 tests collected (2 pre-existing
errors surfaced by newly collected files; both changed files collect cleanly).
Ruff lint: all checks passed on both modified files.
