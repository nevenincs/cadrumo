---
tags:
  - '#exec'
  - '#code-dedup-sweep'
date: '2026-07-25'
modified: '2026-07-26'
step_id: 'S06'
related:
  - "[[2026-07-25-code-dedup-sweep-plan]]"
---




# Rule the bucket-manifest version gap in its own decision record under the durability framing, a fourth persisted format hardcoded at create and passed through on save and read with no version gate of any kind, so a manifest written by a newer application is accepted silently

## Scope

- `storage/bucket/_manifest.py`
- `storage/bucket/_manifest_io.py`
- `application/user_profile/_profile_repository.py`
- `new ADR`

## Description

Rule the bucket-manifest version gap in its own decision record under the
durability framing. The parent ADR surfaced it as a fourth persisted format read
with no version gate of any kind and deliberately did not fold it in, so this step
existed to stop it rotting in an out-of-scope note.

## Outcome

Ruled `accepted`: `2026-07-25-bucket-manifest-durability-adr`, on the option that
enrolls the format in the floor machinery AND adds the forward ceiling.

The record was drafted by a peer agent and ruled here. It is materially stronger
than the finding that surfaced the gap. Three things it established that the
parent did not: the format's only bump encoded a key-schedule change and rode a
routing chore with nothing positioned to notice; read ingress is singular, which
is what makes a gate cheap; and two enrollment gates now contradict each other for
this format, so no flip mapping can satisfy both until it is enrolled or
reclassified — a latent deadlock rather than a nicety.

Enrollment was chosen over the cheaper reclassification on evidence: the format
fails the regenerable definition on three counts, and that class licenses
delete-and-refuse, which applied to a registration record whose absence reads as
an unregistered bucket on a key-minting path is worse than the skew it dodges.

The ruling engages the record's three declared caveats rather than passing them.
The unsized blast radius is bounded by `PRE_RELEASE` today, and re-sizing the
below-floor arm before the gate ships is made a condition of acceptance if the
regime flips first. The proposed-parent dependency does not block, because the
read-gate half stands whichever way the checkpoint resolves. The threat-model
limit — plaintext, unauthenticated, so no defence against disk write — is endorsed
to survive into the commit message so no later reader mistakes it for a security
control.

The shape also matches what the parent ruling already identified as canonical: the
sealed-archive tier's ceiling paired with a floor. Bringing the manifest onto it
keeps the substrate uniform instead of adding a fourth convention.

## Notes

Two items the record holds outside itself are endorsed as deliberately held rather
than lost: `bucket_dek` needs its own owner-gated record rather than being bundled
into a manifest decision, and a save-writer field loss on absolute session minutes
is a separate defect on the same format belonging to the session-lifetime surface.

This step closes the plan at 6/6. Of its six steps, one was authored here (the
vacuity-proof gate), one ruled here, and four were delivered by peer agents and
closed on verification rather than trust.
