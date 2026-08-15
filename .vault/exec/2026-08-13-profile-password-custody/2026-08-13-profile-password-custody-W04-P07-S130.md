---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:0d8bc28da88d43d9c067554a9500740284695fe1d57a00446b65ec8348943c8e'
step_id: 'S130'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium rule whether the private retirement sidecar in the custody package should be enrolled in the durability inventory, since it carries its own schema version and reads regenerable as a crash-window artefact for an interrupted session-key swap, but is private and unrecognised by the storage taxonomy so enrolling it would assert a format boundary nothing else acknowledges, and it is exactly the kind of neighbour that gets enrolled by pattern-matching because the formats beside it just were

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/ and src/cadrumo/core/compatibility_lifecycle.py`

## Description

- Read the two-part nested-format boundary and the sidecar's real write, read and recovery path before ruling.
- Rule format-hood on the boundary test, then argue the class from what an unreadable journal costs.
- Enrol it, bind it to its version constant, and teach discovery about a file the path registry does not define.

## Outcome

**Verdict: ENROL, classed `REGENERABLE`.** Both halves of the boundary test
hold, so it is a format; and the class is argued from loss, against the grain of
every neighbour it sits beside.

**Format-hood.** Independent grammar holds: the journal declares its own version
constant and its own field set -- a profile id and the exact predecessor and
successor receipt bytes -- and a reader needs THAT version, not the session
receipt's, to interpret the document. Durable readback holds: its own bytes are
written to the operator's disk beside the session receipt, and the crash
recovery path parses them back through their own strict model, refusing a
foreign version before acting.

**The row's counter-argument, answered rather than set aside.** That the sidecar
is private and unrecognised by the storage taxonomy is a fact about the constant
NAME and about the taxonomy, not about the bytes. The taxonomy's silence has
already been shown here to be an artefact of nothing enumerating the tree
against the inventory: three capsule formats sat outside it while a retired
plaintext manifest sat inside. So "nothing else acknowledges this boundary" is
the same silence, not evidence.

**The class, argued from loss and against the neighbours.** Every capsule format
beside this one is `DURABLE`. Pattern-matching would therefore have produced
`DURABLE`, and that is wrong. What the journal uniquely records is the INTENT of
a key swap the process died in the middle of: which of two OS-keychain secrets
is now the orphan. Everything else it names is either already on disk or already
in the keychain. An unreadable journal therefore strands one keychain entry and
blocks the recovery that would have revoked it -- a hygiene cost on a session
whose own receipt is already classed regenerable, not lost taxpayer bytes.

The decisive half is the other direction. The journal names which session key to
revoke, and acting on a half-understood one could revoke the LIVE key rather
than the retired one. Tolerating a doubtful reading is strictly worse than
discarding it, and delete-and-refuse is exactly what `REGENERABLE` contracts for.

**Three further formats were enrolled in the same change**, carried in from the
boundary ruling that pre-answered their format-hood and left their classes open.
The legal-hold and filing-retention owner snapshots and the derived custody hold
evidence all gate a DESTRUCTIVE operation, and that is what decides them: an
absent snapshot and an unreadable one produce the same refusal, so discarding a
doubtful one blocks an erase, while tolerating one that half-parses can report
zero open cases or zero retained filings and permit the erase the record exists
to prevent. All three are `REGENERABLE`, each on its own ground -- filing
retention because it also projects an already-durable encrypted catalogue, legal
hold explicitly NOT as a cache since nothing in the tree derives an open case
identifier, and the hold evidence because nothing ever reads its file back at
all.

**Discovery had to learn about files it could not see.** Enrolling these
immediately reddened the enrollment gate, which enumerates the live format set
from the path registry and read three correct declarations as stale ones. None
of the three has a `FILE` path definition: the journal's location is derived
from the session receipt's own path, and the two snapshots sit under owner
subdirectories the owning authority joins. That is precisely the gap the gate
already documents for secure-object payloads, and the same remedy applies -- a
fourth, hand-listed discovery source, anchored on a live storage category and
carrying a stated reason per entry. Its weakness in the omission direction is
written into it rather than left to be discovered.

## Notes

The custody tree is held by another agent, so the sidecar itself was read
only. No production change was needed there: the enrolment gate strips a leading
underscore when it discovers constants, so the private name was already visible
under its public spelling and only the inventory tables moved.

Two constants WERE named, in the evidence and filing packages, because the two
owner snapshots versioned themselves with a bare literal and a format with no
named constant is invisible to the binding gate. That is the same move the
rental-register step made and for the same reason.

The unclassified-format count moved down by one rather than by three: only the
journal was ever visible to that gate, and the two snapshots went from invisible
to enrolled without passing through it.
