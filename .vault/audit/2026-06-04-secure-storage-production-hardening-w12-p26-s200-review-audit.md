---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:e11e362334178141d742ce7c41de481bf63c7f73d5a31ba2205e5d00a8a7dbbc'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S200` Review

## S200-001 | PASS | IVA compensation history already uses secure-bound runtime defaults

`IvaCompensationHistoryRepository` inherits `SecureBoundRepository` and declares
the registered `IVA_COMPENSATION_HISTORY_NAMESPACE` sensitivity/schema contract.
The current secure-bound base resolves its default repository through the active
profile bucket runtime and refuses missing or mismatched storage sessions.

No additional production edit was required for `AFR-098`.

## S200-002 | PASS | Runtime isolation and refusal coverage exists

`test_runtime_migrated_repositories.py` covers `IvaCompensationHistoryRepository`
in both missing-session and route/session-mismatch refusal parametrizations, and
also verifies active-profile isolation for saved IVA compensation period states.
Focused IVA compensation history tests cover the domain projection and registered
error envelope behavior.

## S200-003 | FIXED | IVA compensation guard errors now use localized exception routing

Supervisor review found raw formatted exception strings in the IVA compensation
history API boundary and the adjacent pure carry-forward year-range guard. The
implementation now raises the existing core-derived exception classes with
`translated_message` locale keys and structured context for:

- out-of-range IVA compensation years;
- duplicate seed attempts;
- non-Modelo 303 filed observations;
- non-decimal submitted casilla values.

The error registry now points the Modelo-boundary and seed-conflict error codes
at the same localized keys. Locale entries were scaffolded and set through
`python -m aeat.locales`; the scaffold command also normalized nearby existing
catalog leaves, and the locale audit remains clean.

The adjacent live IVA history capture wrapper already carried a locale key but
also supplied a raw fallback `message`. That fallback was removed and the
wrapper now supplies structured context only.

Because the same shared-worktree file already carried live IVA hardening hunks,
the commit also cross-commits those intersecting changes: standalone IVA capture
entrypoints execute inside the active-profile storage span, and persisted
acquisition failure context now redacts sensitive diagnostic keys before storage.

## S200-004 | PASS | Convention hygiene

No new broad exception handlers, monkeypatches, fakes, mocks, skips, xfails,
naked environment access, tautological tests, `noqa`, or `pragma` suppressions
were introduced. The updated tests assert real raised exception metadata and
runtime repository behavior rather than mirroring business logic.

Validation:

- the historical check passed with 13 tests.
- the historical check passed.
- the historical check passed with 2 selected tests.
- the historical check passed with 4 selected tests.
- the historical check passed with 10 tests.
- the historical check passed with 5 tests.
- the historical check passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: subagent review remains unavailable because the reviewer agent hit
the account usage limit earlier in this run. Host review found no remaining
critical, high, medium, or low findings in the S200 slice.

Disposition: close `AFR-098`.
