---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:23d39001e30cb1bf771ad2fbbb62235f7b3fa7342b320dce472cb921c8fb5827'
step_id: 'S83'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the session-receipt tamper test actually reach the authenticated-data check it exists to cover

## Scope

- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_persisted_session_roundtrip.py`

## Description

- Establish that the authentication branch is reachable at all before assuming
  the test merely needs re-pointing.
- Tamper through the canonical encoder so the record stays byte-canonical and the
  authentication check is genuinely evaluated.
- Make the assertion name the refusal it actually received.

## Outcome

The tamper-detection path is now exercised for the first time. The test
previously re-encoded the receipt with a plain serializer, which broke
byte-canonicality, so the canonical-bytes refusal returned several checks before
the authenticated-data check was ever evaluated. Production was correct
throughout; what was missing was any coverage at all of the branch the test is
named for.

**The reachability question was not a formality and it separated two opposite
remedies.** The associated data binds eight fields, and the idle deadline is one
of them, so a byte-canonical receipt carrying an altered deadline genuinely
reaches the unwrap and genuinely fails there. Had that field NOT been bound, the
correct conclusion would have been the reverse of the row's premise: the test was
right to fail and the defect was in production, a tamperable session lifetime.
That branch was live rather than hypothetical, which is the whole argument for
asking reachability first.

A second judgement shaped the fixture: the deadline is EXTENDED rather than
shortened, so the record still passes the idle-expiry check that sits above the
unwrap. Shortening it would have produced a passing test that was really an
expiry refusal wearing the tamper name -- green for the wrong reason, and
indistinguishable from success.

Verified independently: 23 passed across the module, including the keychain-lane
case that the lane-reachability repair had exposed.

## Notes

**The bite proof is the most consequential artefact this step produced.**
Unbinding the idle deadline from the associated data -- precisely the
vulnerability the test exists to catch -- does not merely leave a forged receipt
undetected. It returns `resumed=True`: an operator-extended session lifetime
accepted in silence, with no refusal at all. That is what the test now guards and
what it could never have caught in its previous form.

The assertion now reports the refusal actually received rather than only that the
expected one was absent, so a future regression to an earlier branch names itself
instead of failing opaquely. The original diagnosis took a full investigation
precisely because the failure said only that the wrong refusal arrived, not which
check had produced it.

Production was untouched, as the row anticipated. The defect was entirely in the
proof, and it had been invisible twice over: the test could not reach its own
subject, and until the keychain lane was given a path that named its directory,
it did not run at all.
