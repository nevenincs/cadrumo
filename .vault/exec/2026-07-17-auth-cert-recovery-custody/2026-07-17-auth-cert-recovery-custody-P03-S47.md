---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S47'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---




# Emit non-secret bucket events for passphrase change and the recovery-code create, rotate, and recover mutations, degrading the trail to a logged no-op when profile storage is locked so it never gates the mutation

## Scope

- `src/cadrumo/application/user_profile/_custody.py`

## Description

- Add four closed-set custody event members to the bucket event type enum: passphrase
  changed, recovery code created, recovery code rotated, secret store recovered. The
  stems stay English as generic custody vocabulary with no AEAT surface.
- Add one module-private emitter in the custody service that resolves the active
  bucket, derives the content-addressed event id, and appends through the existing
  bucket event-history repository. This reuses the emission idiom the sibling profile
  lifecycle service already owns rather than introducing a second authority.
- Emit from all four durable mutations. The enrollment emission is placed immediately
  after the atomic envelope install and before the separate, non-atomic manifest-flag
  write, so a crash between the two still leaves evidence of the enrollment that
  actually happened.
- Carry only non-secret witnesses in payloads: the recovery fingerprint already
  exposed on the public result record, the rotated flag, the store location.
- Degrade the trail to a logged no-op when no profile is selected or the profile store
  is locked, catching only the typed storage-readiness refusal so every other failure
  still raises.
- Add real-behaviour regressions over a real bucket runtime and real encrypted file
  secret store, with no test doubles.

## Outcome

All four mutations now leave a queryable trail readable through the bucket history
verb. Five new tests pass, stable across three randomized-order runs.

Each event test asserts an empty before-state and a single correctly-typed
after-state, so removing an emission fails it. The leak guard asserts per mnemonic
word rather than the joined phrase, so a payload leaking a fragment fails.

`ruff check`, `ruff format --check`, and `ty check` clean on the touched files. The
recovery-lifecycle suite passes 5 of 5, matching its established baseline.

## Notes

The first implementation made the trail a hard dependency and broke the
recovery-lifecycle suite: the emitter raised the storage-readiness refusal whenever no
bucket session was open. This was a genuine design defect, not merely a test failure.
The secret-store recovery operation runs precisely when the operator cannot unlock a
profile, so a mandatory trail would have made recovery depend on the very access it
exists to restore, and would have failed an already-durable custody mutation after the
fact. The emitter now degrades and a dedicated regression pins that behaviour.

Known consequence, deliberately not closed here: because the event history is
per-bucket encrypted storage, a cold recovery performed with no profile unlocked
records no event. Covering that case needs an audit sink outside per-bucket storage,
which touches the sensitive-data storage boundary and is a separate decision rather
than an implementation detail.

Two lower-severity items from the originating review remain open by its own
assessment: recovery plaintext is carried in immutable bytes and strings so it cannot
use the substrate's zeroise primitive, and the recovery-enrollment manifest flag can
desync from the envelope on a crash. Neither was in this Step's scope.
