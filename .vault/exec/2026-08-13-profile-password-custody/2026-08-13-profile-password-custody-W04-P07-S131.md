---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:bd1cb8865dfd757ad9afab907a2b9db0ff3174b237a59d2dc80e9618d799ae22'
step_id: 'S131'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium argue a durability class for the active-profile pointer, which reads regenerable because an operator can re-select a profile, except that a lost pointer on a multi-profile store requires the operator to know which profile was active and the application cannot rebuild that knowledge

## Scope

- `src/cadrumo/core/_bucket_pointer.py and src/cadrumo/core/compatibility_lifecycle.py`

## Description

- Read the pointer record, its writer, and the two-rung resolution chain before classing it.
- Resolve the row's tension explicitly rather than restating it.
- Confirm the enrolled class and the argument standing in the inventory.

## Outcome

**Verdict: `REGENERABLE`, and NEITHER horn of the row's tension is what
decides it.** "The operator can re-select" does not make the pointer
regenerable, and "the application cannot rebuild the knowledge" does not make it
durable. The durability class is not a measure of recovery cost; it states which
response to an UNREADABLE record is correct.

**The tension is real and both halves are true.** Resolution has exactly two
rungs -- an in-process override set by the profile flag, and this file -- and
the pointer exists precisely because the answer cannot be read out of encrypted
state without already knowing it. So the application genuinely cannot derive the
fact. On a multi-profile store, recovery genuinely does require the operator to
remember which profile was active. Recoverable by the operator is not the same
as regenerable by the application, and this record does not lean on the easy
claim that it is.

**What decides it is the asymmetry of the two failure directions.** A missing
pointer produces an immediate, visible refusal: the read path treats invalid
TOML and validation failure as hard failures rather than as "no active profile",
specifically so it cannot silently fall back to root storage. The operator is
told, and re-selects. A TOLERATED pointer produces a silent wrong answer: every
subsequent read and write lands in a bucket the operator did not choose, which
on a multi-profile store means another taxpayer's encrypted slice. One direction
costs a prompt; the other corrupts custody without announcing itself.

`DURABLE` is the promise to keep reading older shapes of a record. Making that
promise here would oblige the code to parse a pointer it does not fully
understand -- the exact tolerance the module already refuses by design.
`REGENERABLE` is the class whose contract is delete-and-refuse, which is what
the pointer's own read path already does. The class follows the code's existing,
correct behaviour rather than asking it to change.

**Loss, stated plainly.** When the pointer stops being readable, what is lost is
one fact -- which profile was last selected -- and the cost is one operator
re-selection at the next command. No encrypted record becomes unreadable, no
key is stranded, and no taxpayer data is destroyed. The pointer names a bucket;
it does not prove the bucket exists, hold a manifest, or carry any content of
its own.

## Notes

The enrolment and its argument were already standing in the inventory when
this row was picked up, having reached the tree inside a peer's broad sweep
commit while the row was still open. The record was verified against the live
resolution chain rather than accepted on sight: the two rungs, the hard-failure
read semantics and the single `POINTER_SCHEMA_VERSION` binding were each
re-read. The standing argument is correct and is left as it is; this record is
the reasoning it was missing.

One stale statement was noticed in the pointer module's own docstring, which
still describes an application-layer scanner deriving records from per-bucket
manifests. That format is retired and de-enrolled. It is prose rather than
behaviour, and it sits at the edge of this row, so it is reported rather than
rewritten here.
