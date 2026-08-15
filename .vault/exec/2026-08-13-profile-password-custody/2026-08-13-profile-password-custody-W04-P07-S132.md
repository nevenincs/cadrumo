---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:651b38c265b2b5e3aeaa76c456d6ad290a7142afbffd4bae3b62987c3f847380'
step_id: 'S132'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium argue a durability class for the AEAT authority session record and the two Cl@ave metadata records, which are the artefacts on the far side of the session vocabulary split and carry real recovery cost when unreadable, each needing its own class rather than one ruling covering the trio

## Scope

- `src/cadrumo/adapters/outbound/aeat/ and src/cadrumo/core/compatibility_lifecycle.py`

## Description

- Read all three metadata records, their version constants and their resume paths.
- Rule each one separately, on what its own unreadability costs.
- Confirm the trio clears the nested-format boundary rather than riding its container's floor.

## Outcome

**Three verdicts, not one.** All three land `REGENERABLE`, and the point of
arguing them separately is that they differ in re-establishment cost by a wide
margin and land in the same class anyway -- which is itself the evidence that
cost is not what the class measures.

**Certificate session metadata: `REGENERABLE`.** Its entire content is a
revalidation binding -- a storage-state digest, an idle deadline, and the
certificate thumbprint, subject and NIF that produced the capture. Not one of
those is stored only here: the certificate lives in the operator's own OS store,
and every other field is observed again the moment authentication runs. What is
lost when it stops being readable is the ability to PROVE that a captured
browser state still belongs to the certificate that made it -- and the
authenticator's own answer to a non-current version is already refusal.
Resuming without that proof is the exact failure the record exists to prevent,
so tolerating a doubtful one is worse than discarding it. The cost is one
re-authentication.

**Cl@ve Móvil metadata: `REGENERABLE`, and this is the one where classing by
cost is most tempting.** Re-establishing it needs the operator's phone and a
fresh AEAT verification code -- a human step the certificate flow does not have.
That cost is real and it is not the test. The record still holds nothing
unreconstructable: the verification code it carries is spent the moment the
login completes and has no value on any later read, and the landing URL, the
identity and the deadlines are all observed again on the next login. The hazard
is on the read side -- a record parsed under the wrong grammar could yield an
idle deadline that extends a session AEAT no longer considers live, and the
resume would then be attempted against dead browser state. Discard-and-re-login
is correct.

**Cl@ve Permanente metadata: `REGENERABLE`, and the least contested of the
three.** It is the headless credential flow: identity, landing URL and deadlines
are re-observed on the next login with no human step at all. No field here is
the only copy of anything. Saying that plainly is what keeps the other two
rulings from reading as a block verdict -- three records with three quite
different re-establishment costs, ruled one at a time, converging because the
question asked of each was the same and had nothing to do with cost.

**Boundary check, because all three are nested shapes.** They live inside one
encrypted session envelope and share a single secure-object namespace. Being
inside an enrolled container does not put their grammar under that container's
floor: each declares its own version constant, each is parsed back through its
own typed model on resume, and the fact that one namespace backs three
independently versioned payloads is the clearest available proof that a
namespace is not a format.

## Notes

The AEAT adapter tree is held by another agent and was read only; no change
was needed there. The three enrolments and their arguments were already standing
in the inventory, having reached the tree inside a peer's broad sweep commit
while this row was still open. Each was re-derived against the live records
rather than accepted: the three version constants, the certificate resume's
explicit version refusal, and the shared-namespace arrangement were all
re-read before the classes were confirmed.

One shape worth noting and deliberately not changed: the certificate metadata
pins its version as a type constraint that restates the number its own default
already binds from the constant. That is a second statement of the number, but
it fails loudly at the next construction rather than silently, so it is out of
scope for the detector rowed separately and is recorded here instead.
