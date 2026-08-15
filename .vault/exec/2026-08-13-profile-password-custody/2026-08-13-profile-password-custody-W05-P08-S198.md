---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:735fb5d6e076b5d4806529476052632f35848e790d475b132c238a83168da9ea'
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

### The fix

The inventory now separates two kinds of capsule member. The custody records --
the password envelope, the DEK sentinel, the label projection, the commit record,
the recovery envelope -- are write-once canonical JSON and are covered by the
digest exactly as before. The three database paths, the database file and its
two sidecars, are members whose bytes track whether a connection is open rather
than what the capsule holds, and they are outside the digest.

The excluded set is derived from the storage taxonomy's bucket-database-file
member rather than restated as literals, because a capsule directory IS a bucket
directory and the engine resolves the same member. Membership is three exact
paths, never a directory prefix and never a suffix rule, so a foreign file
dropped under the database directory stays fully covered.

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

### The gates were shown to bite

An out-of-tree pytest plugin, loaded by path so no tracked file was mutated,
reverted the digest narrowing and reran the suites: five cases reded, including
the end-to-end logged-in deletion. A second mode widened the exclusion to the
whole database directory, the lazy alternative, and reded the foreign-file case
and the derived-set case. The two refusal cases correctly stayed green in both
modes, since reverting the fix makes the guard stricter, not weaker.

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

### A narrowing that must be recorded, not buried

The digest no longer covers rows written into the capsule DATABASE between
preflight and execution. That coverage is not recoverable at this layer: the
database's logical content is readable only through the DEK, which a deletion
deliberately never holds, and its raw bytes are a function of connection state.
Presence is still checked; content is not. The standing goal asks that a
destructive local operation act only on what the operator confirmed, and this
excludes the largest single artefact from that promise. A follow-up that could
close it without re-preparing is a second, separate digest over the database
family captured at the moment of revocation and required unchanged until removal
-- which would cover the highest-risk window, another process writing to a
profile after its session was revoked. That is a persisted-journal shape change
and is deliberately not made here. The narrowing is documented in the inventory
type's own docstring so the next reader meets it where the decision lives.

### Peer sweep captured this work

Between the fix landing in the working tree and verification completing, a peer
session's broad sweep commits captured all four files under other step
identifiers. The commit subject describing the change as excluding the
write-ahead and shared-memory sidecars is an inaccurate account of it: the main
database file is excluded too, which is the whole substance of the measurement.
Nothing was reset or rewritten.

### Ambient red, none of it from this row

A peer's in-flight uncommitted work in the custody service introduced a new error
subclass without its error-code registry entry, which hard-blocked pytest
collection tree-wide for a period and killed one suite run mid-flight. It settled
on its own and was not touched here. That work is entirely in the capsule CREATE
path and does not overlap the delete path changed here.
