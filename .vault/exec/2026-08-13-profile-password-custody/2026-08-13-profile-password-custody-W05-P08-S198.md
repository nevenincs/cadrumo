---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:10e1e79c9cdd129c7ea417934d3154e4817311961fa5c05f9b569c820d572072'
step_id: 'S198'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh stop the profile deletion transaction invalidating its own preflight, since a live login holds the capsule database open so its write-ahead and shared-memory sidecars are inventoried into the prepared deletion marker, and the first act of execution revokes the session which checkpoints and removes exactly those sidecars, so the source-marker re-inventory can never match its own prepared digest and a profile the operator is signed into cannot be deleted at all, which the configuration reset path reaches directly by running prepare and confirm and delete with no prior session close

## Scope

- `src/cadrumo/application/user_profile/_custody_service.py and src/cadrumo/application/config_reset.py`

## Description

- Reproduce the refusal at HEAD with a standalone out-of-tree probe before changing anything.
- Measure the per-entry inventory drift the revocation causes, which corrected the assumed cause.
- Narrow the capsule inventory digest to the byte-stable custody records in `_inventory.py`.
- Derive the excluded path set from the storage taxonomy's bucket-database-file member.
- Make the inventory witness count and measure the covered set, not the wider observation.
- Add adapter coverage for the classification rule and application coverage for the real chain.
- Prove the guard bites in both directions with an out-of-tree pytest plugin.

## Outcome

### The reproduction, confirmed

The probe ran green at HEAD and printed the whole chain. A live login holds the
capsule's own database connection open, so the walk saw seven files including
both write-ahead sidecars. The prepared digest covered all seven. The delete's
first destructive act, revoking the live profile secret, closed that connection;
the walk then saw five files and a different digest. The transaction refused
itself with a transaction conflict reporting that the capsule inventory changed
after the delete preflight. A profile the operator was signed into could not be
deleted, and the configuration reset path reaches exactly that sequence.

### The measurement that changed the fix

The assumed cause was the two sidecars. It was measured instead, and the
assumption was incomplete in a way that matters: across the revocation the MAIN
database file also drifted, from 12288 bytes to 94208, because a checkpoint
folds the write-ahead pages back into it. Excluding only the two sidecars would
have looked correct, passed a shallow reading, and left the deletion still
refusing. Every other capsule member was byte-identical on both sides.

### Why the capsule DATABASE is excluded, argued rather than asserted

This is the part of the change that weakens a guard on a destructive path, so
it is argued here and not left to a commit subject.

WHY. Excluding the main database file is forced, not a convenience, and that
was settled by running the counterfactual rather than by reasoning about it.
The narrower shape -- exclude only the two write-ahead sidecars and keep the
database fully content-covered -- was applied through the out-of-tree plugin
and the logged-in deletion was re-run under it. It refused, with the same
conflict as the original defect: the prepared local deletion marker no longer
matches source custody. The reason is that closing the connection CHECKPOINTS
the sidecar's pages into the main file, measured growing from 12288 to 94208
bytes with no logical write between the observations. Holding that file's
bytes constant across a transaction whose own first act closes the connection
is not strict, it is unsatisfiable: it is the identical self-invalidation this
row exists to fix, one file over.

The same instability exists on the create path, not only on delete. The
restore flow writes a supplied database into the stage and then OPENS it to
authenticate it before publication, so the staged capsule's inventory is
subject to exactly the same checkpointing. The exclusion is therefore load
bearing in both transactions rather than tolerated in one.

WHAT STILL GUARDS IT. Two things, and the honest answer is that neither is
content. First, the database is carried as a PRESENCE member: the digest covers
its path though not its bytes, so a database that vanished or became a
directory between preflight and execution moves the digest and refuses. That
guard was added in response to this question -- the first shape of the fix
dropped the database entirely, and the docstring's claim that presence was
still checked was not true of the code. It is now, and a case proves it.
Second, every other member remains byte-exact, so the identity of the capsule
-- its commit record, its password envelope, its DEK sentinel, its label
projection -- cannot change unnoticed.

WHAT AN OPERATOR WOULD SEE. Nothing. If a concurrent process wrote rows into
the capsule database between the operator confirming and the deletion
executing, the deletion proceeds and destroys them without a refusal or a
notice. Nothing else catches it either: this inventory has exactly one reader
in that window, the deletion itself. That is the true cost of the exclusion and
it is recorded as a limitation rather than described as a trade-off.

### The fix

The inventory now separates three kinds of capsule member. The custody records
-- the password envelope, the DEK sentinel, the label projection, the commit
record, the recovery envelope, and anything not named below -- are write-once
canonical JSON and are covered by path AND content, exactly as before. The
capsule database is covered by path only. Its two write-ahead sidecars are not
covered at all, because their very presence is a statement about whether a
connection is open.

The presence member and the content members are projected into the digest with
different shapes -- a path alone versus a path with size and hash -- so the two
can never be confused for one another.

Both collections are derived from the storage taxonomy's bucket-database-file
member rather than restated as literals, because a capsule directory IS a bucket
directory and the engine resolves the same member. Membership is exact paths,
never a directory prefix and never a suffix rule, so a foreign file dropped
under the database directory stays fully content-covered.

The walk itself is unchanged: it still observes and reports every regular file,
still refuses links, reparse points and non-regular entries, and still enforces
its entry and byte bounds over everything it saw. Only the digest narrowed, and
the inventory carries the covered subset alongside the full observation so the
two are never confused.

The inventory witness bound into the journal was changed to count and measure
that covered subset. This is necessary, not cosmetic. The delete compares whole
witnesses for equality between preflight and execution, so a file count taken
over the wider observation would still have refused the deletion through the
count even with the digest narrowed -- and would have refused any deletion whose
session merely timed out between preflight and execution.

### What was NOT needed

The configuration reset path required no change at all. Its erase step is
exactly prepare, confirm, delete on the capsule lifecycle, so the inventory fix
restores it with no edit to that module and no collision with the
auth-revocation work in flight there.

### Alternatives weighed and rejected

Closing the session before the preflight was rejected on a stronger ground than
the race it moves: the preflight runs BEFORE the operator confirms, so revoking a
live session there logs out an operator who then declines, making a preview
destructive.

Re-preparing after the revocation was rejected because the confirmation is bound
to one specific inventory the operator echoed; re-anchoring it mid-transaction
would absorb whatever else changed in the same window and make the confirmation
a formality.

Widening the comparison to a tolerance was rejected outright. This is the guard
on an irreversible local destruction, and a tolerance on it is indistinguishable
from no guard.

Reusing the existing transient-file helper in the bucket-maintenance package was
considered and rejected on three counts. It is dead code, defined and never
called. Its rule is wrong here: it names lock and temporary files and the shared
memory sidecar, but not the write-ahead sidecar and not the database file, so it
would have reproduced exactly the incomplete fix the measurement ruled out. And
it is a private application-layer helper, which a persistence adapter may not
import. A comment records why the classification lives where it does.

### Proof in both directions

Direction one, at the application layer with a real registration, a real login,
a real capsule and a real encrypted store: a profile the operator is signed into
now deletes through the public lifecycle, and its capsule directory is gone.

Direction two, three ways. A durable custody record rewritten through the
production rename writer between preflight and execution still refuses the
prepared deletion and leaves the capsule standing. A custody record altered or
removed under the marker still moves the digest. And at the exact call site that
used to false-fire -- the source-marker verification that runs after the
revocation -- the same journal now passes on the transaction's own checkpoint
and still refuses when a durable record is altered underneath it.

### The negative proofs are not vacuous, and that is measured too

A "still refuses when custody content changed" proof means nothing if the file
it mutates is one the digest deliberately stopped covering. Every negative case
here perturbs the label projection or the password envelope, both content
covered, and each application-level case now ASSERTS that the member it is
about to mutate is content-covered before mutating it, so the property cannot
rot into vacuity when the covered set next changes.

That assertion was itself tested. A plugin mode demotes the label projection to
presence-only, which is precisely the state that would make those proofs
vacuous, and both application-level refusal cases red under it. No negative
case touches the database or its sidecars.

### The gates were shown to bite

Five out-of-tree plugin modes, loaded by path so no tracked file was mutated.
Reverting the narrowing entirely reds six cases including the end-to-end
logged-in deletion. Excluding only the sidecars, keeping the database covered,
reds the same deletion -- this is the counterfactual that settles why the
database is excluded. Widening to the whole database directory reds the
foreign-file case and the vanished-database case. Dropping the database instead
of carrying it as a presence member reds the vanished-database case. Demoting a
covered record to presence-only reds both refusal proofs. Every mode reds the
derived-set case, since all of them change what the taxonomy pins.

### Verification

The custody-transaction and reset suites ran sequentially with the integration
lane explicitly selected, because the default marker selection would have
executed zero cases in the integration modules and printed green. Full output
was written to a file and read back from disk.

544 passed, 34 failed. Every one of the 34 was then re-run with the fix reverted
through the out-of-tree plugin: 32 failed identically, so they are ambient and
predate this row. The two that differed were re-run again on their own at the
current tree and all five cases in that module passed, so they were transient
churn from a peer's mid-edit state during the long run, not a regression. No
custody adapter case and none of the cases added here appear in the failure
list.

The formatter, linter and both type checkers pass on every changed file.

## Notes

### This row composes with the displaced-session retirement, and does not touch it

The create transaction now retires the DISPLACED profile's session
acceleration immediately before publishing the pointer, through the same
revocation primitive the delete transaction calls. That primitive is therefore
invoked from two transactions rather than one, which is worth checking against
a row whose whole subject is the delete's revocation step.

Nothing here touches it. This row changed what the marker INVENTORIES, not what
the revocation does or when it runs. The revocation module and the custody
service are both unmodified by this row -- the service carries no commit of
mine at all -- so the retirement's ordering constraint, that a crash may leave
retirement done and the pointer unmoved but never the pointer moved and the
receipt live, is untouched and the recoverability leak it closed cannot be
reintroduced from here.

The one place the two do meet is the create path's own inventory comparison,
and there the exclusion is required for the same reason as on delete: the
restore flow opens the staged database to authenticate it before publication,
so the staged capsule checkpoints exactly as the committed one does. The create,
restore, rollback and displacement suites were run to confirm it.

### A correction to this record's own earlier claim

An earlier draft of this record, and the docstring it described, stated that
the database's presence was still checked while its content was not. That was
not true of the code as first written: the database was dropped from the digest
entirely, so a database that vanished between preflight and execution would
have gone unnoticed. The presence member exists because that claim was
challenged and checked. The claim is now true and a case proves it, but the
gap between what was written and what was implemented is recorded rather than
quietly closed.

### A narrowing that must be recorded, not buried

The digest no longer covers rows written into the capsule DATABASE between
preflight and execution. That coverage is not recoverable at this layer: the
database's logical content is readable only through the DEK, which a deletion
deliberately never holds, and its raw bytes are a function of connection state.
Presence is still checked; content is not. The standing goal asks that a
destructive local operation act only on what the operator confirmed, and this
excludes the largest single artefact from that promise. What survives is the
database's presence and every other member's bytes; what does not is its
content, and no other check covers that window.

A follow-up that could close it without re-preparing is a second, separate
digest over the database family captured at the moment of revocation and
required unchanged until removal -- which would cover the highest-risk window,
another process writing to a profile after its session was revoked. That is a
persisted-journal shape change and is deliberately not made here. The narrowing
is documented in the inventory type's own docstring, and pinned by a case that
asserts the digest does NOT move on a database content change, so the gap is
executable rather than merely written down and cannot be silently forgotten.

### Peer sweep captured this work, under a subject that mis-describes it

Between the fix landing in the working tree and verification completing, a peer
session's broad sweep commits captured all four files under other step
identifiers: commit 8105b692c9, subject "fix(custody): exclude WAL/SHM sidecars
from the deletion-preflight digest (W04.P07.S101)", and commit 570b236661 for
the tests.

That subject is recorded here because it is currently the only history-level
description of a change to a safety guard on a destructive path, and it is
wrong in the way that matters. The change does not exclude the write-ahead and
shared-memory sidecars; it excludes those AND the capsule's own database file,
which is the entire substance of the measurement and the only part that
weakens anything. A reader trusting that subject would believe the profile's
actual encrypted content is still covered by the deletion marker. It is not.
The row identifier on the commit is also not this row. Nothing was reset or
rewritten.

### Ambient red, none of it from this row

A new error subclass landed in the custody service without its error-code
registry entry and hard-blocked pytest collection tree-wide for a period,
killing two suite runs mid-flight and causing two spurious failures in the
displacement suite that pass cleanly on re-run. It was subsequently registered.
It came from the displaced-session retirement row, not from this one and not
from this row's scope; the custody service carries no commit from this row at
all.

Separately, a fixture-ownership collision in the shared profile-capsule test
helpers was reported as being worked in parallel. It is test infrastructure
rather than a production path here, and it is named so that any capsule
destination collision seen in the reset suites is attributed there.
