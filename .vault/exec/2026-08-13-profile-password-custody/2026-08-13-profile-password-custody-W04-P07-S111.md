---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:36a3f0be250ecfbda85d22845e2586b612b89ac0506f6f40dd7ea971a604288f'
step_id: 'S111'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium author the decision record for which custody a bucket is enrolled in and pin the defect with a failing regression that reaches an actual record read through the sanctioned door, stating both the resolver-reads-stored-custody option and the rejected mint-a-second-wrapped-copy option with the exposure-widening argument that defeats it, and establishing whether any profile on real disk is currently in the unopenable state since that decides whether a migration question exists at all

## Scope

- `.vault/adr/ and src/cadrumo/adapters/persistence/storage/master_key/tests/`

## Description

- Scaffold and author the decision record for which custody a bucket is
  enrolled in, stating the adopted resolver-reads-stored-custody option and the
  rejected mint-a-second-wrapped-copy option with the exposure argument that
  defeats it.
- Restore the test name the sibling record's rejection deleted, rebuilt around
  the whole door so it reaches an actual record read.
- Add the pre-authentication refusal proof that makes the login step
  load-bearing.
- Add the anti-tautology proof over the persisted custody envelope.
- Re-inspect the live default store read-only to settle whether a migration
  question exists.

## Outcome

**Lead with the measurement: the defect the Step asks to pin does not exist.**
The corrected end-to-end measurement is recorded under S110. A bucket created
through the sanctioned door opens after authentication, and the mechanism the
claim rests on has been deleted from the tree.

**The regression is therefore green, deliberately, and this is the substantive
departure from the Step as written.** The Step asks for a failing regression
pinning the defect. Landing a red test here would assert a state the tree does
not hold — which is precisely the error the sibling record was rejected for,
wearing the clothes of rigour. The campaign's convention for a genuinely held
defect is the tree-wide "asserts a GAP, not a contract" form, and it was
inspected before this decision rather than after; it does not apply, because
there is no gap. A search of the campaign's plan and execution records surfaced
no other held-defect module to match against.

What the Step's spirit actually asks for — a proof that reaches an actual
record read through the sanctioned door — is delivered, and it is the artefact
whose absence let the wrong claim be made twice. Three tests, because one
passing readback proves less than it appears to:

- Create, authenticate, then assert decryptability through the namespace
  integrity probe, which unwraps every profile row under the session key and
  returns counts rather than plaintext: readable greater than zero, unreadable
  exactly zero.
- Assert the **same two calls** refuse before authentication with the shared
  `errors.storage.runtime.not_ready` key. Without this a door that never locked
  would satisfy the first test equally well.
- Anti-tautology: overwrite the persisted custody envelope and lose the login,
  proving the readback is served by material on disk rather than by anything
  the create span left in process memory. The refusal names the current format
  rather than reaching for an older one, which is the no-legacy posture pinned
  as a test.

**No migration question exists.** The live default store was inspected
read-only and is unchanged from the sibling record's count: four buckets, all
pre-capsule, 6,250,496 bytes of `db/cadrumo.db`, each carrying a retired
manifest and a retired keystore entry, with no capsule material of any kind
anywhere beneath the store. Zero capsule-era buckets exist on real disk, so the
population the Step asks about is empty. The four are already owned by the
campaign's authorised destructive reset and are untouched here.

## Verification

- The three new tests pass sequentially: `3 passed`.
- The whole `storage/master_key` suite is green sequentially: `221 passed`.
- `ruff format`, `ruff check` and `ty check` all clean on the new module.
- The new module contributes nothing to the tree-wide gates that are red at
  HEAD from concurrent sweeps: zero occurrences across the 1498-line
  import-hygiene scan output.
- The pre-authentication and corrupt-envelope refusal types were measured
  before being asserted, so neither assertion was written from a guess.
- The regression is immune to the ambient sequential-registration handover
  defect by construction, and this was checked rather than assumed. The
  anti-tautology test expects a login to FAIL, so it is precisely the shape
  that could pass for the wrong reason. It pins the specific
  `ProfileCustodyRecordError` and the current-format phrase, which the
  handover refusal — a different exception type entirely — cannot satisfy. An
  earlier draft caught a bare exception and would have been vulnerable to
  exactly that substitution. The three tests were also confirmed free of the
  handover refusal in their captured run output.

## Notes

Nothing was minted, migrated, repaired or deleted; no cryptographic parameter
was touched. The read-only store inspection opened no bucket.

The regression uses public facades only. An earlier draft reached into a
private module of the profile package for a record store; it was rewritten
against the secure-object repository's integrity probe instead, which crosses
the same decrypt boundary without a cross-package private import.
