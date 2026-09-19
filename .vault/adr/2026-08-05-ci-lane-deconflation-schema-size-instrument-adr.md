---
tags:
  - '#adr'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:70ceaba517bbc8c76696205fe2b7101ac3490112a68a9b764fbe1e6beaaf4ae7'
related:
  - "[[2026-08-05-ci-lane-deconflation-overview-calendar-payload-adr]]"
  - "[[2026-07-08-mcp-progressive-discovery-adr]]"
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - '[[2026-08-05-ci-lane-deconflation-step-check-attribution-audit]]'
---
# `ci-lane-deconflation` adr: `the gate measures a real target and names the wrong one` | (**status:** `accepted`)

## Problem Statement

The per-verb output-schema size gate was challenged as a proxy that had diverged from its
target. Its docstring states the case against itself plainly: structured output double-emits
as text plus structured content at roughly twice the tokens, so the gate "bounds the per-verb
output-schema size — **the static proxy for the structured content a verb emits**".

If that is the target, then suppressing schema metadata reduces the proxy without reducing
the target, because titles and descriptions never appear in structured content. Under the
gate's own stated purpose, the metadata suppression this campaign proposes is gaming the
instrument. That objection was raised, is correct on its premises, and was not waved away.

The question referred here was whether to fix the instrument to measure emitted content, and
whether a proxy diverging this far is worth keeping.

## Considerations

**The premises are true and the conclusion does not follow, because there are two targets and
the gate's docstring names only one.**

- **Target A — per-call structured content.** Double-emitted, scales with rows returned,
  charged on every call. This is what the docstring names.
- **Target B — per-session definition size.** The output schema is transmitted in the tool
  listing, once per session, and `2026-07-08-mcp-progressive-discovery-adr` records the
  July-2026 fact that a client defers tool loading past roughly 10K definition tokens. Schema
  bytes are therefore a cost in their own right with a real client threshold behind them.

The gate measures schema size. Against target A that is a proxy, and a weak one: schema size
is fixed while content scales with row count, so a verb returning three rows and one returning
three thousand measure identically. Against target B it is not a proxy at all — **it is a
direct measurement of the quantity that matters.**

So the instrument is not broken. It is mislabelled, and the mislabelling is what makes a
legitimate reduction look like gaming.

## Considered options

**Fix the gate to measure emitted content.** Rejected as stated, and the reason is
structural rather than effort: emitted content size depends on how many rows a call returns,
which does not exist at the time a static gate runs. The gate's docstring already records
that it is "intentionally static ... a cheap always-on lock". A static measurement cannot
bound a runtime quantity; attempting it produces a second proxy, not a measurement.

**Replace the gate.** Rejected. Under the corrected label it measures its target exactly, and
target B is a real cost with a published client threshold.

**Keep it and take the free bytes without examining the objection.** Rejected explicitly.
This was the available convenient answer and it would have left the instrument's own docstring
asserting something false about it, which is how the next reader re-derives the gaming
objection from scratch.

**Relabel it and rule on each target separately.** Adopted.

## Constraints

Descriptions genuinely are transmitted in the tool listing, so they are a real component of
target B and excluding them from measurement would understate a real cost. Titles are equally
transmitted. Neither appears in structured content, so neither bears on target A.

## Implementation

### R1 — Relabel the gate: it bounds definition size, not a proxy for emitted content

The docstring's claim that schema size is "the static proxy for the structured content a verb
emits" is withdrawn. The gate bounds the serialized size of a verb's output schema, which is
transmitted once per session in the tool listing and is a cost in its own right per
`2026-07-08-mcp-progressive-discovery-adr`.

This is the load-bearing ruling and it costs one docstring. Everything else follows from it.

### R2 — Metadata suppression is a legitimate reduction, not gaming

Under R1 the objection dissolves rather than being overruled. Suppressing auto-generated
titles removes bytes that are genuinely transmitted, so it reduces the measured quantity
because it reduces the real cost — a measured 198,806 characters across 297 verbs. That is
the definition of a real saving rather than a proxy manipulation.

The distinction that makes this honest rather than convenient: **it would still be gaming if
the target were target A**, and the reason it is not is that the target was misnamed, which is
an argument about the instrument rather than about the remedy. Had the gate genuinely bounded
emitted content, this ADR would have refused the suppression.

### R3 — Target A is unbounded, and this gate never bounded it

Nothing today bounds the size of what a verb actually emits per call. That gap is real and is
not closed by this record. It cannot be closed by a static schema gate for the reason given
above, so if it needs closing it needs a runtime bound, where the row count exists. Recorded
as an open gap with a named shape rather than left as an implication of the relabel.

### R4 — The docstring-links collision is a tension, not a contradiction; do not exempt prose

Descriptions are 24.6% of the `overview.calendar` schema and derive from docstrings that
`core-struct-docstring-links` actively mandates. The two disciplines do pull on the same text.

They do not contradict. That rule mandates cross-links for navigability — that a module
importing a core struct cross-references it — not verbose prose. A concise docstring carrying
a `:class:` role satisfies it. So the tension is real and resolvable by writing shorter
docstrings, not by exempting descriptions from measurement.

**Do not exempt them.** They are transmitted, so under R1 they are part of the cost, and a
gate that stops counting a cost it is meant to bound has re-acquired the exact defect this
record is correcting.

### R5 — The budget number is calibrated to a moment, not derived from the threshold

18000 was set "with headroom above the current maximum". It is not derived from the ~10K
definition-token client threshold, and the relationship between a per-verb character budget
and a whole-listing token threshold is not established here. Recalibration is therefore a
live question, and one input is now known: roughly 4734 characters of every verb's schema is
the shared envelope spine, which no payload change can touch, so a per-verb payload allowance
is about 13300 rather than 18000.

## Rationale

The objection was correct on its premises and the premises were incomplete. That is a
different failure from a wrong objection, and it deserves a different response: not overruling
it, but supplying the fact it lacked. Both parties were reasoning from the gate's docstring,
and the docstring is the thing that was wrong.

This is the third instance in this campaign of one artefact describing itself inaccurately and
sending careful readers to a wrong conclusion — after a plan row that named four broken tests
where three shared a cause, and a consistency check whose name implied coverage it did not
have. The pattern is worth naming: **an artefact's self-description is evidence about intent,
not about behaviour**, and where the two diverge the behaviour is what other decisions must be
built on.

## Consequences

- One docstring changes. No gate logic changes, no budget changes, no verb changes.
- The metadata suppression proceeds on its own merits with the gaming objection resolved
  rather than outstanding.
- Target A remains unbounded and is now recorded as a named gap rather than an unexamined
  assumption that the existing gate covers it.
- Any future argument that a schema reduction is "gaming the proxy" must first establish
  which target it is arguing about.

### What this record does not establish

Whether target A needs bounding at all. Nobody has measured what a large call actually emits,
so the gap is named but its severity is not.

Whether 18000 is the right number under the corrected label. R5 opens it; nothing here closes
it.

Whether the ~10K client threshold applies to this deployment's tool listing as a whole, given
progressive discovery may mean not every verb's definition is loaded. The threshold is cited
as the reason definition size is a real cost, not as a computed budget input.
