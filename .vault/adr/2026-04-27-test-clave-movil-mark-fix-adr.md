---
tags:
  - '#adr'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
related:
  - '[[2026-04-27-test-clave-movil-mark-fix-research]]'
  - '[[wgergely-aeat-436]]'
  - '[[wgergely-aeat-439]]'
---

# `test-clave-movil-mark-fix` adr: Re-mark Cl@ve Movil tests as live read | (**status:** `accepted`)

## Problem Statement

`src/aeat/auth/test_clave_movil.py` was marked as `unit` even though its authentication-flow tests drive `ClaveMovilAuthProvider` through the Cl@ve Movil login, persistence, probe, and resume paths. That breaks the marker contract for the default unit suite and forced contributors to rely on an ignore workaround documented in issue 436.

## Considerations

The affected current tests are `test_qr_flow_writes_sidecar_and_storage_state`, `test_non_qr_fallback_fills_dni_form`, `test_non_qr_fallback_rejects_missing_fecha`, `test_probe_uses_existing_sidecar_without_invalidating_on_failure`, and `test_resume_from_fresh_sidecar`.

The provider path under those tests reaches `_fresh_login_locked()`, where the browser session navigates AEAT selector URLs, enters Cl@ve Movil, waits for the phone-approval landing, and persists storage state. The local stand-in implements the necessary browser protocol methods today, but the behavioral surface is the live AEAT authentication flow rather than isolated computation.

The project marker convention requires module-level access and domain markers. Splitting access markers per function would violate the convention and leave a mixed-access module. Moving the whole file to `live_read` preserves the rule, even though some pure helper tests in the file become live-selected by module scope.

The searched repository surfaces no longer contain `--ignore=src/aeat/auth/test_clave_movil.py`, so there is no code or documentation workaround to delete in this checkout.

## Constraints

No production provider code may change for this issue. Live AEAT submission remains permanently forbidden and this work touches only read-side authentication tests. The no-mocks discipline rules out cassettes, monkeypatching, `vcr`, and HTTP mocking.

## Implementation

Change the module-level marker to `pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]`.

Add a top-of-file docstring note that the module is live-gated by `AEAT_LIVE_TESTS_ENABLED=1`.

Add a small autouse fixture using `aeat.cli._live.requires_live_enabled()` so direct collection of `src/aeat/auth/test_clave_movil.py` with `-m live_read` skips cleanly when the operator has not opted in. This is needed because the live opt-in hook in `tests/conftest.py` is not loaded for `src/aeat/...`-only collection.

## Rationale

Path A is chosen. It aligns the marker with the AEAT Cl@ve authentication boundary and avoids new test infrastructure. Path B, recording a cassette or stored HTTP interaction, is rejected because it would add forbidden cassette/mock-style machinery and would not improve the marker contract under the current project rules.

## Consequences

`just test` uses the default unit marker selection and deselects this file. Explicit `live_read` collection skips when `AEAT_LIVE_TESTS_ENABLED` is false and runs when the operator opts in.

Operator-only verification for the live path:

1. Set `AEAT_LIVE_TESTS_ENABLED=1`.
2. Ensure Cl@ve Movil identity settings are configured in `env/.env`.
3. Run `uv run --no-sync pytest -m live_read src/aeat/auth/test_clave_movil.py -q`.
4. Approve any Cl@ve phone prompt if the provider is run with a real browser session instead of the in-file protocol stand-in.

CI should remain unset for `AEAT_LIVE_TESTS_ENABLED`; the default unit suite no longer selects the module.
