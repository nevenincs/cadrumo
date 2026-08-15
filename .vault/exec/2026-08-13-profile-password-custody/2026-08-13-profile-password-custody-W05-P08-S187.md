---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e9ce48c7694b88c2b3e3d26b68e3acd0b38f1442d40a7a7b9701ce30fabf3dd0'
step_id: 'S187'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule how a reset clears authority state for a target it has not unlocked, since revoking the authority browser session genuinely requires the key because that session is an encrypted row inside the bucket, while a reset holds locks on targets whose key nobody holds, making the auth phase structurally unreachable in exactly the way the retention assessment was before it was rewired, and seventeen reset failures now rest on this one refusal

## Scope

- `src/cadrumo/application/config_reset.py and src/cadrumo/application/auth/`

## Description

- Inventory every auth artefact a profile owns and measure, for each, whether
  removing it needs the profile's key and whether the capsule's destruction
  reaps it.
- Rule what the auth phase does for a target it cannot unlock, and record what
  it could not reach instead of reporting a clean sweep.
- Clear the key-free half for absent targets too, which the phase skipped
  entirely.
- Prove the ruling bites in both directions from outside the repository.

## Outcome

**The inventory is the ruling, and it has three rows rather than the two the
row assumes.** Measured against a real capsule in a temporary root, not
reasoned about. The AEAT browser session and the auth workflow state are
encrypted rows in the bucket's own database, INSIDE the capsule: reading or
deleting either without a session refuses, and destroying the capsule removes
the database file holding them. The acquisition lock is a plaintext file in the
token directory, OUTSIDE the capsule: it clears with no session at all, and the
capsule's destruction leaves it exactly where it was. The third row is the one
nobody had placed. A certificate-source secret is stored outside the capsule,
in the storage root's shared secret substrate, and its lookup digest is derived
from the profile's own key -- so it is neither addressable without the key nor
reaped by the deletion. Out-of-bucket AND key-bound, which is the combination
that decides this whole step.

**The offered hypothesis holds for one half and fails for the other.**
In-bucket auth rows do die with the capsule, and the proof is a file inventory
taken before and after a real custody deletion rather than an assertion: the
bucket database, the password envelope, the recovery envelope and the key
sentinel all disappear together. The same measurement shows the
certificate-secret ciphertext and its index entry standing untouched
afterwards. Had this step adopted the hypothesis rather than testing it, the
reset would have cleared the locks, declared itself done, and left key-bound
authority material on disk with nothing recording that it had.

**The ruling.** A locked target gets the key-free half only: every provider's
acquisition lock is cleared explicitly, because nothing else will, and no
in-bucket revocation is attempted, because the capsule's destruction ends those
rows and the revocation could not open them anyway. A target whose custody
session IS open keeps the full revocation, since that is the only way the
out-of-bucket secret can be reached at all. Which half runs is decided by asking
the storage span the same question it answers on entry, rather than by copying
its reuse test or by catching its refusal after the fact.

**Nothing is claimed that did not happen.** The phase label says auth was
cleared, a claim about content that only one of the two halves earns, so the
target now carries a typed clearance recording which half ran, which locks it
removed, and how many out-of-bucket secret records it removed -- a count when a
session was open, and an explicit unknown, never a zero, when it was not. The
unknown is honest twice over: the reset cannot enumerate those records without
the key either, so "none removed" and "none existed" are indistinguishable from
where it stands.

**Nothing survives that should not, on the one axis where survival is
avoidable.** The locks are gone. The in-bucket rows go with the capsule. The
certificate-secret ciphertext does outlive the erase, and the test asserts that
it does rather than pretending otherwise -- together with the fact that makes
it tolerable rather than merely tolerated: every wrapping of the key that would
decrypt it, the two capsule envelopes and the session receipt outside the
capsule, is asserted absent in the same test. The residue is unreadable, and it
is declared.

**The refusal is untouched, and the honest reason to leave it is that removing
it was never the fix.** No revocation was made to succeed by skipping what it
names. The reset stopped asking for one it cannot have.

**Both directions proved from outside the repository.** Forcing the
reachability answer to "open" reds the locked-target test and both reachability
tests; forcing it to "locked" reds only the test asserting an open session is
recognised. Neutering the key-free lock clearing reds the lock assertion alone.
Three runtime plugins on the interpreter path, no tracked file mutated, so a
peer's sweep could not capture the mutation.

## Notes

**An absent target was skipped entirely and should not have been.** The phase
marked a dangling target auth-cleared without doing anything, on the reasoning
that there is no capsule to clear auth from. Its acquisition locks were never
inside the capsule, so they survived every reset -- one file per provider, per
dangling target, accumulating.

**The seventeen failures this row was handed are gone, and they were not the
last wall.** The custody-session refusal appears nowhere in the reset suites
now. Five reset-suite tests still fail and none of them is that refusal; each is
a distinct wall the auth wall had been hiding, and each belongs to a surface
this row does not own. The deletion preflight demands the legal hold owner's
facts and no production door writes them -- only the filing owner has a
creation-time writer -- so a real profile cannot be deleted at all until one
does; the reset suite forges that fact locally and says so at the site. The
operator's recorded retention override is consumed by the reset's own backstop
but never reaches the custody transaction, which independently refuses the same
target with no override channel. And on Windows the capsule's atomic no-replace
rename fails with an access violation when the erasing process previously
opened that profile's database, which the command-line entry point does for the
active profile as a matter of course. Each deserves its own row.

**Two verification choices worth defending.** The locked-mode proof is built on
a DANGLING target on purpose: it exercises the auth phase end to end while
depending on nothing downstream of it, so it stays green while the deletion
walls above remain open and reds only for reasons this row owns. The unlocked
mode is proved at the auth surface rather than through a whole reset, for the
same reason -- a reset cannot currently complete for a target that has a
capsule, and proving a branch through a path blocked elsewhere proves nothing.

**The journal grew a field and needs no version bump.** The config-reset journal
is enrolled as a regenerable persisted format, so it carries no durability
floor, and the clearance is optional on a target that never cleared auth.

**Attribution of what did not go green.** Across the six reset suites the count
moved from eighteen failing to seventeen, with three tests added and passing;
seventeen of the eighteen were the auth refusal and none of the seventeen
remaining is. The authority suite is otherwise green apart from two
certificate-source tests failing while creating a capsule on a second storage
root with a Windows directory-anchoring error, reproduced with this step's other
change neutered, so neither is claimed here. One reset test fails on the Windows
file-in-use error this worktree's backing share is known for.
