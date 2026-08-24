---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:183011344e06ff77da406868c0c5cc5ee97bcc20dd587427d624c5f32c105dd3'
step_id: 'S224'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Extend every machine-secret refusal and dispatch-state snapshot to include session and receipt artifacts while preserving unread-channel and cross-platform harness evidence

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py`
- `src/cadrumo/adapters/persistence/storage/custody/_acceleration_receipt.py`

## Description

- Keep the generated portable/POSIX and Windows HANDLE harnesses on one
  logs-only durable snapshot predicate.
- Include session, receipt, retirement, root, and lock artifacts in every
  refusal and dispatch-state equality witness.
- Repair the lifecycle mutation that the retained lock witness exposes without
  a test-only cleanup or lock deletion.
- Preserve unread-channel, descriptor closure, HANDLE bootstrap, and POSIX
  inherited-descriptor behavior.

## Outcome

The previous `.lock` exclusion was not an acceptable fix: it hid a real
empty-session-lock mutation. Corrective commit `5e51632799` retains every lock
artifact in both generated harnesses and the host-side snapshot helper, while
excluding only diagnostic logs. The witness then exposed and verified the
production repair: session mint, resume, delete, and idle renewal now share
the re-entrant root-to-leaf lock order, so an established logged-out resume
observes absence without creating the per-session lock.

Commit `a26f609f2e` also moves deterministic malformed mint and renewal input
validation before root locking and adds cold-root no-artifact regressions. The
independent-process resume/mint case proves ordering; on a keychain-less host
it proves serialization and honest refusal rather than claiming successful
resume visibility.

The final authoritative Windows machine-secret integration run passed **70
passed in 497.07s**. Focused receipt/race/validation tests passed **9**, and
Ruff plus targeted ty were clean. No mocks, patches, skips, xfails, lock-file
deletions, or snapshot exclusions were introduced.

## Notes

The page-level profile-setup materialization command remains blocked before
sequence evaluation by independently owned Modelo 303/322 registry conflicts.
This is a registry residue, not an S224 witness exception, and is recorded in
the S223 close review.
