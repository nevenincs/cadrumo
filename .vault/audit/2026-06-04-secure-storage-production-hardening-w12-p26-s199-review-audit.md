---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:0b5c3d2da884fab16627f985513aa8f130eeefcc5596e3f725744da446feacc0'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S199` Review

## S199-001 | FIXED | Auth session state no longer derives plaintext token paths

`storage_state_paths()` previously composed `Settings.aeat_token_dir` with the
active profile and provider stem. That left the application-level auth-session
identifier tied to a plaintext filesystem directory even though the concrete
session store now persists encrypted secure objects.

The fix routes session identity through `aeat_auth_session_storage_state_path()`,
which returns a stable logical key under `.aeat/auth/sessions/`. The `settings`
parameter is retained for API compatibility, but the encrypted object identity is
active-bucket/provider scoped and does not drift with `aeat_token_dir`.

## S199-002 | PASS | Active-profile and provider partitioning remain explicit

The storage-state tests now pin certificate, Cl@ve Móvil, default-provider, and
active-profile switching behavior against logical keys. They also assert that two
different `aeat_token_dir` values produce the same encrypted object key.

The certificate authenticator and Cl@ve Móvil provider now call the same core
helper, so provider save/resume paths and application session probes cannot drift
apart.

Cross-commit note: the dirty Cl@ve Móvil provider/test files also contained
representation-action centralization through external constants and typed
initial selector-navigation timeout coverage. Those hunks were validated and
kept with the provider-side S199 alignment rather than reverted.

## S199-003 | PASS | Convention and exception hygiene

No new exceptions, broad exception handlers, monkeypatches, fakes, mocks, skips,
xfails, raw user-facing strings, or naked environment access were introduced.
Locale work was not required.

## S199-004 | HONEST DEBT | Existing provider-orchestration tests still use stand-ins

The retired test still contains an inherited
duck-typed provider stand-in and pyright/pyrefly ignore comments. This S199
slice did not expand that debt. It remains outside the storage-key fix and
should be retired under a separate auth-provider protocol narrowing step.

Validation:

- the historical check passed.
- the historical check passed with 33 tests.
- the historical check passed with 3 tests.
- the historical check passed with 3 tests.

Reviewer note: subagent review remains unavailable because the reviewer agent hit
the account usage limit earlier in this run. Host review found no remaining
critical, high, medium, or low findings in the S199 slice.

Disposition: close `AFR-097`.
