---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:1d63c3433bf97aac3adf529a6570fd783ec471d3bac2c8718628521c8d38b8ce'
step_id: 'S92'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore dedicated coverage for the strong logout close and for session-artefact reaping on profile destruction, since both test modules exist now only as stale compiled artefacts after their sources were deleted in a committed change, leaving the strong close with no dedicated module in its owning package and the deletion invisible to anyone reading the directory

## Scope

- `src/cadrumo/application/user_profile/tests/`

## Description

- Confirmed the row's premise physically: the tests package's bytecode cache
  still carries `test_logout_strong_close` and
  `test_destroy_reaps_session_artefacts` compiled artefacts for three
  interpreter and pytest variants each, with no source beside them. All nine
  such files are untracked build residue; none is tracked.
- Recovered the deleted sources from history rather than reconstructing them
  from the row text. Both were removed in the same commit as the
  profile-record roundtrip proof, `7c062ed17e` ("make the custody capsule the
  sole profile authority"). An earlier delete-and-re-add pair in the history
  is a revert, not a separate loss.
- Read both recovered modules in full and adjudicated every case against the
  current surface before restoring anything.
- Restored two modules in the owning tests package, and proved the restored
  assertions bite by disabling the durable half of the revocation authority
  from a scratchpad pytest plugin.
- Investigated one restored case that would not pass, established its cause
  with a standalone probe, and confirmed it as a live production defect rather
  than a fixture error.

## Outcome

**What the deleted sources actually covered.**

`test_logout_strong_close` had eight cases in three classes. The strong close:
the persisted session record removed and the pointer cleared, with a resume
afterwards refusing; the credential-store half of the split-knowledge pair
removed; the live session key buffers sealed so a retained reference raises;
the failed-login backoff cleared. Idempotence: a second logout a clean no-op,
a logout with nothing signed in a no-op, and a login after logout minting a
fresh session rather than resuming one. And one refusal case: logout refusing
under an explicit per-invocation active-profile override, with nothing torn
down.

`test_destroy_reaps_session_artefacts` had five cases in three classes,
written against a real leak -- 552 orphaned credential-store entries
accumulated on one workstation, because only logout and the login handover
ever reaped and no destroy path did. It covered a tombstoning delete removing
the persisted record and the credential-store half; a physical bucket
directory removal removing the custodied key, including on a pass where the
directory was already gone; and a held-open file handle surfacing as a
domain-typed error rather than a raw operating-system error.

**Per-case judgement on whether the subject still exists.**

Restored, subject live and unchanged in meaning: the pointer and persisted
acceleration removal plus the resume refusal; the session sealing; the
failed-login backoff clearing; the second-logout no-op; the no-session no-op;
and the fresh-authentication-after-logout case.

Restored with a changed entry point: the destroy-side reaping. Every function
the old module called is gone -- there is no lifecycle-span delete and no
bucket-directory removal helper. Destruction is now a prepared, confirmed and
executed custody transaction, and the reap is two receipted owner effects
carried by the login-session module. The concept survives; the surface does
not, so the restored module drives the current transaction and asserts the
receipts and the artefacts rather than the retired helpers. It also adds the
narrowness case the old module never had: deleting one profile must not tear
down an unrelated profile's live session.

Not restored, subject genuinely gone: the logout override refusal. The
override error type no longer exists anywhere in the tree, and the current
strong close performs no override check at all. Restoring the assertion would
mean re-creating a refusal the code does not make.

Not restored, subject live but no longer observable from this layer: both
credential-store-half assertions and the two bucket-directory removal cases
that depended on reading a custodied key back. The public read the old module
used no longer exists; the acceleration secret is now addressed by a session
identifier only the receipt carries, so asserting it would require importing a
private function of the storage custody package from an application test,
which the architecture boundary forbids. The on-disk half plus the resume
refusal decide the same security property and need no credential store, so
every restored case runs in the default lanes instead of behind the keychain
marker. The one existing case that does prove a real minted receipt is
destroyed sits in the custody-transactions module behind that marker, which
every default lane excludes; the restored module is deliberately the half that
needs no such precondition, and says so.

Not restored, subject gone: the held-open-handle error-shape case. It was a
property of the removal helper's error posture, and that helper no longer
exists.

**Cross-process shape: not needed, and why.** The sibling non-resurrection
proof was re-sited across separate processes because revocation only works
where both logins share one process, so an in-process check could pass
vacuously. That reasoning does not transfer here. Every claim in these two
modules is about DURABLE state -- a file on disk, a receipted owner effect, a
pointer -- observed after the acting call returns in the same process that
made it, so a second process could observe nothing the first cannot. The one
process-local claim, the sealed key buffer, is asserted on the concrete
session object the test itself holds, which a second process could not reach
at all. The restored suites are therefore deliberately single-process.

**Proving the restored assertions bite.** A scratchpad pytest plugin, loaded
only through the interpreter path for one run and never applied to a tracked
file, replaced the durable revocation authority with a no-op while leaving the
process-local teardown intact -- so logout still "succeeds" from the caller's
point of view while the persisted acceleration and the backoff survive. Under
it, four of the ten restored cases go red: the acceleration-and-resume case,
the logout backoff case, the second-logout case, and the destroy-side backoff
case. The other six stay green, confirming the break is scoped to the
mechanism those four name rather than a blunt failure of the fixture.

**A live production defect found and handed back, not fixed.** A profile that
is genuinely logged in cannot be deleted at all. The delete preflight
inventories the capsule directory, and a live login holds the capsule's own
database connection open, so the write-ahead sidecars are part of that
inventory. The first step of the delete's execute phase revokes the live
process secret, which closes that connection and removes both sidecars, so the
inventory the transaction re-verifies against its own prepared digest can
never match and the delete refuses with a conflict reporting that the prepared
marker no longer matches source custody. A standalone probe reproduced it
exactly: the prepared digest still matches immediately before the call, the
two sidecars are present before the revocation and absent after, and the
delete then refuses. The production reset path runs precisely this
prepare-confirm-execute sequence with no prior session close, so an operator
resetting the profile they are signed into hits it. Reported to the
coordinating session for a row that owns the delete transaction. No production
file was touched here, and no restored case encodes the broken behaviour as a
contract: the destroy module binds a real live bucket session for the target
without opening the capsule connection, which reproduces the state the reap
exists for while leaving the sidecar question to the row that owns it.

## Notes

Two working-tree hazards, neither of them an action this step took.

A peer session's broad sweep commits captured both restored modules while they
were still being iterated on; they appear in three consecutive authority-grade
sweep commits. No add, commit, stash or checkout was run from here. The
working tree currently matches the committed content, so what landed is the
final version rather than an intermediate one, but the capture was neither
requested nor performed by this step.

The nine orphaned bytecode artefacts were left in place. They are untracked
build residue, and the two restored modules overwrite the relevant entries on
the next run; removing the rest would have touched a third module's residue
for no benefit.

Ambient failures observed in the owning package's wider suite are attributed
separately and are not caused by this work. Separately noted, not touched: the
keychain marker's own description in the packaging manifest points readers at
a boundary drawn in a tests-package conftest that no longer exists in that
directory. The manifest is another owner's file.
