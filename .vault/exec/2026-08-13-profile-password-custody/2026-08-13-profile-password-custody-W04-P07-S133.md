---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
step_id: 'S133'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium classify the roughly one dozen genuine persisted formats the binding gate found unbound

## Scope

- `src/cadrumo/core/compatibility_lifecycle.py`

## Description

- Classify the encrypted profile record first, argued from what is lost when it
  stops being readable.
- Classify the participation index, where its own rule makes REGENERABLE a
  finding rather than a default.
- Apply whatever the first argument establishes to the earlier exclusions.

## Outcome

The profile record is DURABLE and the participation index REGENERABLE, and the
argument behind the first turned out to govern more than its own entry.

**The profile record's version is a SEPARATE durability axis from the secure
object that carries it.** The envelope governs how the bytes decrypt; the record
version governs whether the record inside them can still be read and its lineage
authenticated. A frozen floor on the container does not cover the grammar within
it, so an unreadable record stays unreadable however sound its envelope is. It
holds the taxpayer's own facts, and it has already been bumped once -- so that
axis has been moving unobserved on the most sensitive data the product holds.

The participation index is the contrast that makes the classification mean
something. It is REGENERABLE on the strength of its own contract rather than by
default: a derived read-side cache rebuilt from the finalized revision
catalogue, whose governing rule requires lifecycle correctness to rely on the
live catalogue scan rather than on the index's freshness. Delete-and-rebuild is
therefore the CORRECT response to a version mismatch, which is exactly what the
class asserts. One argued REGENERABLE beside a dozen DURABLE is what stops the
next reader treating the class as a formality.

**The first argument then falsified four of the step author's own earlier
exclusions, and they moved rather than being defended.** Four domain record
shapes had been excused as living inside an enrolled secure object. By the same
reasoning that classes the profile record, being inside an enrolled container
does not put a record's own grammar under that container's floor -- so the asset
register, the investment-goods register and their siblings carry strict version
validators over persisted taxpayer data and need classes of their own. They are
now in the awaiting-classification state with that correction stated in each
entry.

The gate remains green at eight passing with the corrected membership.

## Notes

The self-correction is the part worth carrying. An exclusion argued in one pass
was falsified by an argument made in the next, and the author applied the new
reasoning backwards to their own work rather than letting the two coexist. That
is the opposite of the failure this campaign keeps recording, where a claim
survives because nothing forces it to be re-derived.

It also demonstrates why the awaiting-classification state earns its place: the
four shapes could move OUT of exclusions without the gate going red and without
anyone pretending they had been decided. A binary enrolled-or-excluded design
would have forced a choice between leaving a known-wrong exclusion standing and
breaking the tree.
