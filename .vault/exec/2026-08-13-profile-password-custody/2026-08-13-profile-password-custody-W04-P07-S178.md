---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:ef72d5f1937f62adbf369676033654dd923d41d531a56276a3c435f2e9b9b651'
step_id: 'S178'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh restore the anti-tautology proof for the filing-time snapshot persistence boundary, whose coverage was deleted alongside the profile-record proof in the same cutover commit but which no row has claimed since, its shape being unrelated to the capsule cutover and still live, and which today carries equality roundtrips with no mutation proof at all so a save-drops-field regression there stays invisible

## Scope

- `src/cadrumo/application/user_profile/tests/`

## Description

- Read the closed discovery record that located the deleted proof, then read
  the deleted file itself out of history to see what it covered for the
  snapshot boundary specifically rather than trusting the summary.
- Read the pattern the record names as known-good -- the profile-record
  roundtrip suite and its shared support module -- and reused that support
  module rather than duplicating a fixture, widening one helper by a
  keyword-only argument so an exclusion set stays a statement about the model
  under proof.
- Wrote a strict roundtrip and anti-tautology suite for the snapshot boundary
  against real adapters, populating every defaultable field non-default.
- Broke the production boundary twice from outside the repository and
  confirmed the proof reds each time, then restored.
- Ran lint, format and type checks on every file touched.

## Outcome

**Bite proof first, because it is what makes the row real.** Two independent
breaks were applied from a scratchpad pytest plugin, loaded only through the
interpreter path for the duration of one run. No tracked file was edited at
any point.

The first break made the canonical hash content-INSENSITIVE: the derivation
was replaced with one that ignores the facts entirely, so a corrupted payload
re-derives a digest matching the persisted one instead of being refused. That
is the literal "loader recomputes instead of refusing" defect the proof exists
to catch. Under it, exactly the two refusal cases go red -- the substituted
fact value and the deleted defaultable window bound -- while the five other
cases stay green. The break is therefore scoped to the mechanism those two
cases name, not a blunt failure of the fixture, and the assertions bind to a
real and individually necessary code path.

The second break made the WRITER lossy: the repository's save was replaced
with one that strips the snapshot's creation instant from the envelope before
encrypting, the save-drops-field half of the regression. Under it three cases
go red -- the strict equality roundtrip, the defaultable-field sweep, and the
dropped-instant case, the last because the field it means to remove is already
absent and its mutation raises. All three reds are attributable to the broken
writer.

Both proofs bite. Nothing here passes with the boundary broken.

**What the deleted file actually covered for this boundary.** The deleted
proof carried two boundaries in one file. The profile-record half is fully
restored and exceeded elsewhere. The snapshot half is what this row owns, and
what the deleted file had for it was a save-load-equality probe with no
mutation proof and a hand-picked field list -- weaker than what replaces it
here, in the same way the record proof's replacement was.

**What the suite proves now.** Seven cases against real adapters: a real
bucket runtime with its own on-disk database, the real master-key provider
behind the secure-object repository, and the production serializer pair.
Nothing is mocked, stubbed or patched.

Strict pydantic equality across the real save and load cycle is the first
case. The fixture reuses the shared populated facts, each carrying a distinct
non-default provenance token and a closed effective-dated window, so a
boundary that dropped a window or re-defaulted a provenance cannot survive the
equality assertion.

The defaultable-field sweep is derived from each model's own fields rather
than a maintained list. The snapshot's own defaultable surface is almost empty
-- one pinned schema identifier and one clock-defaulted instant -- so a
snapshot-only sweep would have been vacuous. The sweep therefore also runs
over every persisted fact, which is where the regression would actually hide,
and it asserts the facts collection is non-empty first so the per-fact loop
cannot pass by having nothing to iterate. The two excluded fields are each
proven separately: the schema identifier by a dedicated case showing the model
refuses any other value, so the exclusion is a statement about the model
rather than a concession; the instant by exact reproduction of a pinned
literal, since comparing a clock default against a freshly evaluated one would
differ for any snapshot whatsoever and prove nothing.

Three anti-tautology cases mutate the persisted payload through the same
encrypted write path -- same namespace, same object key, same classification
and schema version the repository's own writer stamps -- so the only thing
differing on disk is the payload. Dropping a required field refuses.
Substituting a fact value refuses, because the load side re-derives the
content-addressing digest and rejects the drift. Dropping a fact's defaultable
window bound refuses for the same reason, which is the harder half and the one
the populated fixture exists for.

**One honest finding worth recording.** The snapshot's creation instant and
its identifier are deliberately outside the canonical hash, which addresses
the profile's content rather than when the snapshot was taken. A payload that
loses the instant on disk therefore loads cleanly with a re-defaulted value:
the load side has nothing to refuse with. That is not a defect, but it is a
gap in what the boundary can detect, and the rule's other branch applies -- so
a seventh case asserts strict inequality, and pins down that everything the
hash does cover crossed intact so the inequality is attributable to the
dropped field rather than to a broken decode. A future change that silently
reconstructed or fabricated that instant would break this case rather than
sail past a suite that only ever checked the refusing fields.

**Shared fixture reuse.** The support module genuinely fitted, so no fixture
was duplicated. Its defaultable-field sweep gained a keyword-only exclusion
argument defaulting to the profile record's own pinned and clock-defaulted
pair, leaving the record suite's behaviour unchanged while letting the
snapshot suite pass its own set. Without that, the snapshot suite would have
inherited an exclusion list belonging to an unrelated model.

## Notes

The ambient defect the row warned about -- a second profile registration in
one process failing in handover recovery -- was never reached: this boundary
needs one bucket runtime and no login at all, so no fixture here creates a
state production cannot produce.

A peer session's broad sweep commits captured the new suite and the widened
support module while they were still being iterated on. No add, commit, stash
or checkout was run from here; the working tree currently matches the
committed content, so the final version is what landed, but the capture was
neither requested nor performed by this step.

The scratchpad plugin used for both breaks lives outside the repository and
was loaded only through the interpreter path. It was never applied to a
tracked file, so a peer's sweep commit could not have captured the mutation.
