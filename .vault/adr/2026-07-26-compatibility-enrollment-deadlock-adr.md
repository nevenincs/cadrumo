---
tags:
  - '#adr'
  - '#compatibility-enrollment-deadlock'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-25-bucket-manifest-durability-adr]]"
  - "[[2026-07-25-compatibility-checkpoint-adr]]"
  - '[[2026-07-25-code-dedup-sweep-rag-inventory-audit]]'
---

# `compatibility-enrollment-deadlock` adr: `the enrollment reference set is derived, and a dormant gate must prove it can fail` | (**status:** `accepted`)

## Problem Statement

Two checkpoint enrollment gates contradicted each other, and no release-flip mapping
could satisfy both. `_CANONICAL_FORMAT_KEYS` in the central gate was a hand-listed
mirror of three format keys; `PERSISTED_FORMATS` had since grown to five DURABLE
formats. The uncovered-durable gate therefore required `bucket_dek` and
`bucket_manifest` to carry frozen floors, while the floor-key gate rejected exactly
those keys as naming no live tier. Both were vacuously green because
`RELEASED_FORMAT_FLOORS` is `None`, so the contradiction was latent: it would have
surfaced at the flip as a gate refusing the correct mapping.

The deadlock raised a second, more general question. Both gates could not fail
today; nor could the upgrade-chain completeness gate, nor an inner-re-stamp
obligation shipped as documentation. This project has twice been burned by gates
reporting green while measuring nothing. What separates an acceptable dormant gate
from a broken one needed a rule rather than a sentiment.

A third defect surfaced from the same review: `ProfileRepository.save` silently
reset the absolute login-session expiry on every write.

## Considerations

- The hand-listed set is itself the defect class this campaign exists to remove. A
  set that must track a declaration goes stale the moment the declaration grows, and
  widening it to five would fix today's contradiction while re-arming it for format
  six.
- Reclassifying either format REGENERABLE would dissolve the deadlock and was
  refused on evidence. That class licenses delete-and-refuse, which for `bucket_dek`
  means destroying every encrypted byte in the bucket. For `bucket_manifest` the
  accepted bucket-manifest-durability record already refused it on three counts.
- A third key-set direction was uncovered by anything: neither existing predicate
  catches a floor key naming a format no declaration governs at all.
- The four dormant gates are not one class. Two are vacuous by a declared repo
  constant; the burned gates were LIVE gates whose instrument was broken.
  Conflating them would either bless the broken class or condemn the dormant one.
- On the save defect, the obvious remedy inverted on inspection. Copy-and-update
  removes the drop hazard but defers validation to the next read, and the
  bucket-scan path swallows manifest read failures, so a deferred refusal is a
  silently vanished profile rather than a caught error.

## Considered options

- **Widen the hand-list to five.** Smallest change. Rejected: it restates a
  declaration by hand, which is what went stale, and it re-arms for format six.
- **Reclassify a format REGENERABLE.** Dissolves the deadlock cheaply. Rejected:
  the classification is a durability decision about taxpayer bytes, not a lever for
  making a gate pass.
- **Chosen — delete the hand-list and derive both directions from
  `PERSISTED_FORMATS` through core predicates.** Makes the deadlock structurally
  unrepresentable rather than resolved, and closes the missing third direction.

## Constraints

- Both formats keep DURABLE. Any change to DEK bytes, wrapping, the schedule enum,
  or a bump of the wrapped-DEK document's `schema_version` is OWNER-GATED and
  outside this record.
- The change must remain vacuously green pre-flip, so it removes the latent
  contradiction without altering present-day behaviour.
- A gate that cannot currently fail is acceptable only under the four criteria
  below. A dormant gate whose logic is an inline expression against a hand-listed
  set fails them by shape, which is what this deadlock was.

## Implementation

Ruled `accepted` on all three decisions by a binding architecture review, and
implemented.

**One — derive the enrollment reference set.** `_CANONICAL_FORMAT_KEYS` deleted. A
new pure core predicate `unknown_floor_keys` closes the third direction, exported
through `cadrumo.core`. The floor-key gate now asserts both `unknown_floor_keys` and
`misclassified_floor_keys` are empty against `PERSISTED_FORMATS`. Landed in
`9059117183` with synthetic non-vacuity proofs driving the real predicates against
the real declaration table, plus a guard that the durable inventory exceeds the
retired three so the proof cannot pass by the inventory shrinking back.

**Two — the vacuous-green rule.** A gate that cannot currently fail is acceptable
iff all four hold: its emptiness follows from a declared constant or registry state
rather than from a scan that might silently match nothing; it declares its dormancy
and what arms it; its discriminating logic is a pure predicate in production code
driven by sibling tests with synthetic reject and accept inputs; and a live gate
fails loudly if the dormant condition ends without it arming. A scan-based gate must
instead prove it scanned. Narrow exception: an obligation unprovable without
fabricating a shape nothing wrote may ship as documentation plus a live detector,
only when a non-vacuous gate pins that detector's application.

Applied: the floor-key gate failed criterion three and is fixed by decision one; the
durable-floor gate passes and is the template; the upgrade-chain gate passes; the
inner-re-stamp obligation passes under the narrow exception, its detector pinned
non-vacuously by the reader-derivation gates, confirmed by reading the scan output
rather than the test names. The vacuity screen stays a SCREEN and is not promoted to
a CI gate — its two declared false-positive classes would make it cry wolf.

**Three — the silent reset and its mechanism.** `ProfileRepository.save` dropped
`session_absolute_minutes`, silently resetting the absolute login-session expiry on
every write. Fixed in `8c461b32d6`; briefly converted to copy-and-update in
`bdbafb3fdc` and reverted in `a8d509e311` on the supplementary ruling. Validated
enumeration stands as the idiom for multi-field carries on a durable format, because
a model-derived preservation test forces a per-field classification decision that
copy-update would make silently.

The reversal exposed the real gap: the five sibling writers mutate via `model_copy`
and therefore wrote UNVALIDATED. Closed once at the single write ingress —
`write_manifest` re-validates before serialising, symmetric to `read_manifest`'s
validating read ingress — which dissolves the enumeration-versus-copy asymmetry at
the root and leaves the idiom free. The preservation gate now covers all six manifest
writers.

The mechanism rule: every same-type read-modify-write writer of a persisted model
carrying defaultable fields owes a model-derived preservation test seeded non-default
AND a validating write ingress. Prefer validated enumeration for multi-field carries,
copy-update for single-field updates. Cross-type codecs may enumerate but must keep
their targets all-required so an omission stays loud. Deliberately no tree-wide AST
gate: the sweep found a one-site class, and a high-false-positive gate is the
instrument rot this campaign removes.

## Rationale

Deriving beats widening because the failure was not the set's contents but its
existence: a mirror of a declaration is a duplicate authority, and duplicate
authorities drift. Deriving converts "the two gates happen to agree" into "the two
gates read one declaration", which no future format can break.

The vacuity rule earns its shape from the distinction the burned gates obscured. A
gate vacuous by a declared constant is knowably dormant and its arming condition is
readable; a gate vacuous because its pattern cannot match is indistinguishable from a
working one. Criterion one is that discriminator, and criterion three is what makes it
checkable rather than asserted.

## Consequences

- Good: the flip becomes representable; the third key-set direction is covered; the
  deadlock cannot recur for a sixth format; every manifest write is now validated
  regardless of idiom; and the vacuity rule gives later authors a test to apply
  rather than a precedent to imitate.
- Accepted cost: a validating write ingress adds a full model validation per manifest
  write. Manifest writes are rare lifecycle operations, so the cost is immaterial
  against a silently vanished profile.
- Outstanding, and NOT closed here: enrolling `bucket_manifest` and `bucket_dek` with
  their floor machinery, both flip prerequisites. The manifest half is specified by
  its own accepted record. The DEK half is declarative — a named current-version
  constant, a floor, and a tier gate — because its document version is already a
  strict `Literal[1]` refusing both drift directions; if it turns out to require any
  change to key bytes, wrapping, or schedule, that is owner-gated and must stop.
- Carried forward for the first `cipher_schema_version` bump: the rotation path
  reconstructs a cipher envelope by enumeration and carries that defaultable field
  explicitly. Latent-benign today because default and current are both 1, so a drop
  would reset 1 to 1 undetectably. The obligation to prove the carry rides that bump
  commit, which the lineage machinery already forces to be deliberate.
- Outstanding: the vacuity screen's 35-hit worklist is untriaged. It needs one pass
  classifying each hit into the screen's own three classes — legitimate-absence,
  off-module-guarded, or genuine missing-proof — with the genuine hits becoming steps.
  Not done here.
- Honest limit: the one-site claim for the reconstruction class rests on an `rg`
  sweep, which is weaker than a read. It claims no other site was found by a pattern
  that found every known site, not metaphysical absence. That pattern is the standing
  re-check at swarm-audit cadence.
