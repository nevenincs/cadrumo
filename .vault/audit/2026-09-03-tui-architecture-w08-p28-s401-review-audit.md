---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:ef19e52bd0fe4c5ee29585891ba6376673e9f501015b0e723422e223162862e7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` audit: `w08 p28 s401 review`

## Scope

Independent review of `W08.P28.S401` against the approved TUI architecture plan, the accepted out-of-process destination protocol ADR, and the resolved S400 review. Reviewed the bootstrap application contract, TUI adapter, their focused tests, and installed child-entry composition for truthful inventory, custody, login, cancellation, registration, secret, authority, and network boundaries.

## Findings

### installed-bootstrap-unwired | high | The coordinator is not reachable from a child-process entry path

`prepare_workbench_bootstrap`, `workbench_login_screen`, `finish_workbench_login`, and `handoff_registration_required` are referenced only by their focused tests and by each other. `launcher.py`, `app.py`, and the TUI module-execution path contain no bootstrap reference. Consequently a real child cannot execute the required recognized-inventory, custody-resume, login, cancellation, degraded-inventory, or zero-profile-registration state machine. The implementation exposes isolated helpers but does not build the installed child-process coordinator required by S401; S400 expressly leaves that ownership to this step.

### installed-bootstrap-unwired-resolved | low | The S401 coordinator now owns the closed bootstrap state machine

Resolved on re-review. `run_workbench_bootstrap` makes one injected preparation and routes only the immutable degraded, empty-registration, resumed-authenticated, login-authenticated, and login-cancelled states. It does not reopen inventory or custody, retain a passphrase, invent profile data, invoke a CLI or dev fixture, or initiate network work. The new focused paths prove each route and refuse every inappropriate side effect. Installed root and account host composition remain deliberately deferred to their separately scoped S384 and S403 work; they are not a remaining S401 defect.

## Recommendations

Wire one installed child-session owner to invoke `prepare_workbench_bootstrap`, route its closed states to the existing login and registration journeys, and continue to the authenticated root only after a resumed or authenticated result. Add a real child-entry test covering recognized resume, login cancellation, degraded inventory, and empty-inventory registration without CLI or dev-fixture imports.

## Verification

Initial focused result: `uv run --no-sync pytest -q -n0 src/cadrumo/application/user_profile/tests/test_workbench_bootstrap.py src/cadrumo/entrypoints/tui/tests/test_bootstrap.py` passed: 8 tests in 2.31 seconds. Initial scoped Ruff check passed. Re-review after the coordinator addition: the same focused command passed 13 tests in 3.24 seconds and the scoped Ruff check passed. The re-review found the coordinator carries no raw passphrase or custody material, uses the canonical profile-summary authority, imports neither CLI nor dev fixtures, and has no network call. The root's external-provider refusal remains outside S401 because root and account host composition are separately planned in S384 and S403.

Final result: **APPROVE**. The prior HIGH finding is resolved; no S401-owned HIGH or CRITICAL finding remains.
