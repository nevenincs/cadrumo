---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e073cab5bd02effee176b4c7709ed8e42e0174e39512b0ed95c1543c9c8d095d'
step_id: 'S28'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Establish what the M303 carry normalisation path actually is

## Scope

- `src/cadrumo/application/calculations/_m303_carry_ingress.py` and its five production
  call sites

## Description

- Enumerate every production caller of the normalisation and validation
  functions, including those that bypass the persistence door's opt-in flag.
- Read each call site to establish what it wants from the path.
- Classify the wants and report whether they cluster.

## Outcome

The wants cluster cleanly, on an axis nobody had named.

Two callers PRODUCE the canonical form. Both are writers, both reach the path
through the persistence door's opt-in flag, and both hold a disposition when they
do -- one from the declaration-type header it passes, one resolved at the filing
boundary.

Four callers ASSERT that the canonical form was already produced. Three are
readers of persisted evidence and one is a gate. **None of them consumes a
normalised value.** The validation function computes the normalised envelope,
compares it against the one it was given, raises if they differ, and returns the
ORIGINAL. Normalisation is used purely as an oracle. So the path is not a
normalise-and-validate pair that grew together -- it is a transform and a
FIXED-POINT ASSERTION over that transform, and the assert side needs no
normalisation capability at all.

That contradicts the prior this step was given, which supposed the readers wanted
normalisation without validation. They want the opposite: validation with the
normalisation discarded.

## Notes

**The assert cluster splits again, on failure disposition, and that split is the
live question.** Three of the four let the refusal propagate. The fourth, the IVA
wallet gate, catches it and returns nothing -- so a non-canonical carry envelope
reaches that gate as ABSENT EVIDENCE rather than as a refusal. A gate that
reports "no evidence" where it means "evidence this build cannot interpret" is
the silent shape this codebase's own rules exist to prevent, and it is
independent of anything this campaign changed.

**Why this row existed at all.** A prior attempt put a filing-boundary
requirement on the shared persistence door and was reverted. The follow-up
assumed the remedy was to move it inside the gated ingress. That assumption does
not survive this census: the ingress is not a filing boundary either, because
four of its six production callers are not filing anything. Establishing that is
a precondition of the decision, not a consequence of it -- the row had been
parked as blocked on the amendment when it is upstream of it.

**The earlier census missed the four because of its shape**, not its reach. It
searched for the door's opt-in keyword, which every writer passes and no direct
caller does, so it could only ever have returned writers.
