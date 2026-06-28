---
tags:
  - '#exec'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-test-clave-movil-mark-fix-plan]]'
---

# `test-clave-movil-mark-fix` execution summary

Implemented Path A by changing `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` from `pytest.mark.unit` to `pytest.mark.live_read` while preserving `pytest.mark.domain_aeat_remote`.

Added a top-of-file docstring note explaining that the module is live-gated by `AEAT_LIVE_TESTS_ENABLED=1`.

Added an autouse `requires_live_enabled()` guard so explicit source-only `live_read` collection skips when the operator opt-in is disabled.

The five current tests that motivated the marker change are:

- `test_qr_flow_writes_sidecar_and_storage_state`
- `test_non_qr_fallback_fills_dni_form`
- `test_non_qr_fallback_rejects_missing_fecha`
- `test_probe_uses_existing_sidecar_without_invalidating_on_failure`
- `test_resume_from_fresh_sidecar`

Leak diagnosis: these tests enter the provider's Cl@ve browser-login, storage, probe, and resume paths. The current code has no provider-internal `aiohttp` or `httpx` bypass; the remote boundary is the browser-driven AEAT Cl@ve flow itself. The hand-written browser-session stand-in mirrors the browser protocol today, but the module is still semantically live-read under the marker taxonomy.

Documentation cleanup: searched `justfile`, `.github/workflows`, `docs`, `tests/README.md`, `src/aeat`, and `.vaultspec/rules/rules`; no `--ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` reference exists in this checkout.

CI runner state: CI should continue running default unit selection with `AEAT_LIVE_TESTS_ENABLED` unset. The module is no longer selected by `-m unit`.

Verification completed:

- `uv run ruff check src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`: passed.
- `AEAT_LIVE_TESTS_ENABLED=0 uv run --no-sync pytest -m live_read src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q`: 14 skipped.
- `AEAT_LIVE_TESTS_ENABLED=1 uv run --no-sync pytest -m live_read src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q`: 14 passed against the current protocol stand-in.
- `just lint`: passed.
- `just typecheck`: passed.
- `just test`: 3805 passed, 13 skipped, 40 deselected.
- `just test-cov`: 80.04 percent total coverage, above the 60 percent floor.
- `just hooks`: passed.

Code review found one unrelated `uv.lock` scope issue from the requested bootstrap upgrade commands. The lockfile delta was reverted; the audit entry is marked resolved.
