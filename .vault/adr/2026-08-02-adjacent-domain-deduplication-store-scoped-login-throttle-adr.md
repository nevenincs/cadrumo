---
tags:
  - '#adr'
  - '#adjacent-domain-deduplication'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:798daad5141670135a08d3be93af36ea4adeeecaab5108fba720adb884b1f7e9'
related:
  - "[[2026-08-02-adjacent-domain-deduplication-fleet-burndown-findings-audit]]"
---

# `adjacent-domain-deduplication` adr: `store-scoped failed-attempt budget for the store passphrase` | (**status:** `accepted`)

## Problem Statement

The failed-attempt budget that stops Argon2id derivation becoming a
passphrase-testing oracle is keyed per bucket, while the secret it guards is one
store-wide file. The two scopes do not match, and the mismatch is not confined to
the one door the fleet burndown flagged.

Three production doors verify the operator's store passphrase by unwrapping the
master key. `login_profile` and `change_passphrase` consult the budget before
deriving; `profile_create_storage_span` does not consult it at all. Closing the
third door needs a scope ruling first, because keying its counter on the bucket
the caller names would meter nothing: the caller chooses that identifier. This
record owns the scope decision. It does not authorise the implementation.

## Considerations

- The secret is store-wide. `FileFallbackMasterKeyProvider` persists `master.key`
  and `master.kdf` under `Settings.cadrumo_secret_store_dir`, whose default is a
  single `var/secrets` directory carrying a per-store salt
  (`_master_key.py:380-406`, `config.py:384`). No bucket identifier participates
  in resolving it.
- The counter is per bucket. `login_throttle_path` requires keystore separation
  and lands the sidecar at `keystore/<bucket_id>/` (`_login_throttle.py:104-109`).
- All three doors verify that same secret through the same call. Login resolves
  `get_master_key_provider(...)` with no bucket argument and calls
  `provider.get_master_key()` (`_login_session.py:440`, `:546`); custody unwraps
  identically (`_custody.py:525`); the create span does the same at
  `_orchestration.py:176-178`.
- Two buckets therefore hold two independent budgets for one secret. Measured:
  six recorded failures against bucket A leave A throttled at the 60 s cap while
  bucket B, testing the same store secret, reports not-throttled with zero
  failures. An operator with N profiles multiplies an attacker's budget by N at
  the correctly-wired login door.
- The create span is unmetered regardless of bucket identity. Measured against a
  provisioned store: six consecutive wrong passphrases each raise
  `MasterKeyPassphraseMismatchError`, the failure count stays at zero, and no
  throttle sidecar is written anywhere under the storage root - whether each
  guess uses a fresh bucket id or reuses one fixed id. A correct passphrase is
  accepted immediately afterwards with no backoff. The positive control (correct
  passphrase, clean store) is accepted, so the refusals genuinely discriminate.
- The channel is the exception, not the clock. Wrong guesses returned in
  0.085-0.146 s and the accepted control in 0.372 s, the difference being the
  bucket provisioning and DEK enrollment that only a successful unwrap reaches.
  This is an unmetered verification oracle; it is not a timing-oracle break, and
  describing it as one would repeat the category error this campaign exists to
  correct.
- The door is operator-reachable, not dead. Seven production call sites exist;
  `register_profile_with_credentials` (`_registration.py:175`) is the one that
  threads an operator-chosen passphrase into the span, and it is reached from the
  credential-first registration screen at `_manager_frontend.py:163`. The other
  six resolve the ambient configured secret.
- Custody already names this decision as out of its own scope. `_throttle_scope`
  states that closing the residual unthrottled path needs a store-scoped counter,
  which is a change to the throttle module's per-bucket contract rather than
  something to improvise there (`_custody.py:457-472`).
- No prior refutation pins per-bucket keying. The throttle's negation-named guard
  tests cover the no-lockout contract only (`test_no_sidecar_is_not_throttled`,
  `test_corrupt_sidecar_is_treated_as_cleared_no_lockout`,
  `test_reset_is_idempotent_when_no_sidecar_exists`); none records store-scoping
  as tried and rejected.
- The lockout ceiling bounds the denial-of-service cost. Backoff caps at 60 s
  (`THROTTLE_BACKOFF_CAP_SECONDS`), there is deliberately no permanent lockout,
  and any successful authentication resets the counter - a contract the module
  documents against NIST SP 800-63B 5.2.2 and pins by test.
- The attacker who can reach these doors can also read the key file. On a
  single-user local CLI, code execution as the operator permits copying
  `master.key` and `master.kdf` and cracking offline at hardware speed with no
  budget at all. The budget's real constituency is the walk-up attacker at an
  unlocked terminal who drives the CLI but does not exfiltrate files.

## Considered options

- **Store-scoped budget, all three doors keyed to it.** Matches the counter to
  the secret; closes the third door and the login-door multiplication together.
  Cost: one attacker's guesses delay every bucket's login, bounded by the 60 s
  cap. Chosen.
- **Per-bucket budget, wire the create span to the created bucket's counter.**
  Rejected: the caller names that identifier, so a fresh id per guess resets the
  meter. It also leaves the login-door multiplication untouched, because that is
  a scope defect rather than a wiring gap.
- **Budget keyed to the secret-store path rather than to any identity.** Kept in
  substance, rejected in name: this is what store-scoped means here, since one
  store directory holds one master key. Naming it after the path would couple the
  sidecar to a configurable location and complicate relocation.
- **Remove or gate the third door.** Rejected: the span is load-bearing across
  seven production call sites, and the unwrap is not incidental to it - enrolling
  a bucket DEK requires the store key, so the verification cannot be deleted,
  only metered.
- **Accept the oracle and document it.** Rejected on reachability. The door sits
  behind an operator-facing registration screen, so it is not the unreachable
  surface that would justify declining. The offline-cracking alternative bounds
  the value of fixing it, but bounding is not eliminating.
- **Change nothing pending a threat-model ruling.** Rejected: the scope mismatch
  is established independently of how the residual risk ranks, and leaving the
  counter mis-scoped keeps two doors wrong rather than one.

## Constraints

- No new dependency. The change is confined to the throttle module's key
  derivation and its call sites; the sidecar format, the backoff curve, and the
  revocable-cache contract are unchanged.
- The sidecar must move out of any single bucket keystore, so
  `login_throttle_path` and its keystore-separation guard change shape. That
  guard exists to keep bucket key material separated from bucket data; a
  store-level sidecar must land somewhere that preserves that separation rather
  than sidestepping it.
- The no-permanent-lockout contract is load-bearing and must survive. A
  store-wide counter without the 60 s ceiling would be a genuine denial of
  service rather than a bounded delay.
- The keyring backend reaches the same doors without deriving from a passphrase.
  The budget must stay meaningful for it without misreporting a keychain refusal
  as a wrong passphrase.
- Pre-release, so existing per-bucket sidecars are deleted rather than migrated.

## Implementation

The throttle gains a store-scoped key derived from the secret-store directory
that holds the master key, and the sidecar moves out of the per-bucket keystore
to a store-level location that preserves keystore separation. `login_profile`,
`change_passphrase`, and `profile_create_storage_span` all evaluate that one
budget before any derivation, record a failure on unwrap refusal, and reset it on
success - the shape `change_passphrase` already implements, applied uniformly.

The create span is the only door that gains new behaviour: it must evaluate
before `provider.get_master_key()` and refuse through the same typed
`ProfileLoginThrottledError` the other two raise, so the refusal carries
remaining-wait seconds on the notice channel like every other throttled refusal.
Its provisioning branch must keep working on a store with no master key yet,
where there is no secret to guess and nothing to meter.

Custody's `_throttle_scope` degradation disappears with the per-bucket keying it
exists to work around: with a store-scoped counter there is no profile selection
to resolve, so the residual unthrottled path for a caller who can clear the
active-profile pointer closes as a consequence rather than as a separate fix.

## Rationale

The knockout is that the budget must be keyed on the secret being tested, not on
the record being opened. Every door here tests one store-wide key; keying the
meter on a bucket makes the budget a function of how many profiles exist and of
which identifier the caller supplies, neither of which constrains an attacker.
The measurement makes this concrete in both directions: the counter bites where
it is recorded, and does not bite on a sibling bucket testing the identical
secret.

The denial-of-service objection is the real cost, and it is bounded rather than
answered. A store-wide counter does let one attacker delay every profile's login,
and an operator mistyping their passphrase does delay their own other profiles.
What makes that acceptable is the ceiling the module already enforces and tests:
60 s maximum, no permanent lockout, cleared by any success. The trade is a
bounded self-inflicted delay against an unbounded guessing budget, and the
existing contract is what keeps the first term bounded. If that ceiling were ever
raised, this decision would need revisiting.

The remaining honesty is about how much this buys. Against an attacker with local
code execution it buys nothing, because the key file is readable and offline
cracking is faster than any API path. It is worth doing because it is cheap,
because it corrects a scope error that is wrong on its own terms at two doors,
and because the walk-up attacker it does stop is exactly the one the login
throttle was built for. It should not be ranked as an urgent remediation.

## Consequences

- One budget for one secret. The failed-attempt count stops being a function of
  profile count, and the third door stops being an unmetered way to test the
  passphrase that the first two meter.
- A shared-fate cost lands on legitimate operators. Failures on one profile delay
  login on the others, up to 60 s. Multi-profile operators - gestores in
  particular - feel this where they did not before, and the refusal message must
  make the store-wide scope legible so the delay does not read as a defect.
- The throttle module's per-bucket contract changes, including its module
  docstring, its keystore-separation call, and the sidecar location. Every test
  asserting the sidecar lands under `keystore/<bucket_id>/` moves with it.
- Custody's scope degradation and its documented residual hole both close without
  a separate change, and the explanatory prose in `_throttle_scope` becomes stale
  and goes with it.
- The create span acquires an authentication refusal it never had, which is a
  behaviour change on a load-bearing path with seven call sites. The
  first-profile provisioning case has no secret to test and must not be metered
  into a refusal.
- A future per-bucket secret would need its own budget. This decision is correct
  because today every door tests one store key; introducing genuinely per-bucket
  passphrases would reopen the scope question rather than inherit this answer.
- Nothing here changes the offline-attack exposure, which remains the dominant
  risk for an attacker with local execution and is not addressable by throttling.
