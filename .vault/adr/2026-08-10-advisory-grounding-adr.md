---
tags:
  - '#adr'
  - '#advisory-grounding'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:ee7af91eccd7c7b657c4e3b94b0e88ef94fa5f8374557f2b40aaa5fd113f60f0'
related:
  - "[[2026-08-10-advisory-grounding-reference]]"
---

# `advisory-grounding` adr: `How a calculation advisory carries its provision` | (**status:** `proposed`)

## Problem Statement

Calculation advisories tell an operator that a specific provision governs their
figure, and they do it in a message string. `CalculationSourceDiagnostic` had no
typed reference fields at all until 2026-08-10, so the prose form was not
carelessness: it was the only shape available. The fields exist now because a
ruling forbade prose for one new advisory, which leaves the tree with one
correct instance and a large untyped remainder and no decision about what the
remainder should become.

The obvious framing is a conversion sweep. The grounding reference measures why
that framing is wrong, and the measurement is the reason this record exists
rather than a plan row.

## Considerations

- **The feared population is empty.** Every provision asserted in prose has a
  legal-catalogue entry, eleven families probed. No advisory cites a provision
  the registry cannot corroborate. Stated first because a later reader noticing
  untyped article literals will otherwise re-run the same investigation.
- The largest population is a PRECISION gap, not a grounding gap: the catalogue
  carries the exact provision and the casilla does not reference it.
- Advisories cite at apartado granularity while casillas carry whole-article
  refs, and the catalogue holds entries at both.
- The one correct instance derives its refs from the casilla and its binding.
  That is right for an advisory about the casilla's own computation and wrong
  for one about an eligibility rule governing its input.
- Five modules hold no revision, snapshot or casilla definition at all.
- Casilla `0613` carries a single ref whose corpus target is a known two-vintage
  excerpt missing the clauses the advisories beside it assert.
- Reference, throughout.

## Considered options

1. **Each advisory declares its OWN provision refs against the catalogue,
   validated at registry build that every id resolves (chosen).** Casilla-derived
   refs are retained only for the computation-describing kind. Costs a per-site
   authoring decision and a build-time validation.
2. **Mechanically derive every advisory's refs from the casilla it addresses.**
   The obvious sweep, and rejected on the measurement: it attaches a coarser or
   partial ref than the claim, so an advisory about art. 81.3 emerges carrying
   whole-article `art-81`. The result is typed, passes every gate, and is less
   precise than the prose it replaced. **Worse than the status quo, because the
   prose does not claim to be corroborated and the typed ref does.**
3. **Leave the prose and add nothing.** Rejected: nothing validates a message
   string, nothing notices when an article is renumbered across a filing year,
   and the operator cannot distinguish a checked citation from a typed one.
4. **Add the finer provisions to the casillas' own `legal_refs` and then derive.**
   Rejected as a category error that would corrupt the registry to serve a
   consumer: a casilla's refs describe what establishes THAT BOX, and appending
   an eligibility rule that governs one of its inputs would make casilla
   grounding mean two different things.
5. **A per-advisory catalogue of message-to-provision mappings.** Rejected: it is
   a second authority over the same fact, kept in sync by hand, and the standing
   architecture rule treats that as a criticality rather than a trade-off.

## Constraints

- No production code lands from this record.
- **ORDERING, and it is a hard gate rather than a note.** The art-81 advisory
  sites MUST NOT be converted until the `ley-35-2006:art-81` catalogue entry is
  repointed off the two-vintage excerpt, or they must be excluded from the
  conversion. Converting first makes them look grounded while citing a document
  that does not contain the rule they state, which is strictly worse than the
  prose. A later implementer holding this record and no memory of the audit will
  otherwise convert them, which is why this is a constraint and not a remark.
- The refs an advisory declares are a TAX REVIEW per site against the provision
  the message asserts, never a lookup. This record rules on the mechanism and
  cannot rule that any particular id is correct.
- Population C is threaded as its own rows. Threading a revision into a module
  that has none is a signature change with its own blast radius and must not
  ride inside a citation change.
- The confirmed false positive is excluded by name, so a later sweep does not
  rediscover it as work.
- A build-time validation that every declared id resolves is a REFUSAL, so it
  states a control proving the legitimate population still passes and does not
  close on the refusal firing.

## Implementation

An advisory declares the provisions it asserts, as catalogue ids, at the site
that makes the claim. Registry build validates that each declared id resolves to
a catalogue entry, which is the check the prose form could never have.

The casilla-derived path is retained and is not deprecated: for an advisory whose
subject IS the casilla's own computation, the existing union of casilla and
binding refs remains correct and continues to mint nothing. The two paths are
distinguished by subject, and the distinction is recorded on the diagnostic
itself rather than left to a reader.

What this record does NOT do: it does not convert any site, does not rule which
provision any advisory should cite, does not touch the twelve modules that assert
nothing, and does not alter casilla `legal_refs` in any registry revision.

## Rationale

Option 1 wins on the knockout that killed option 2, which was the assumed answer
until it was measured. The provision an advisory asserts is a property of the
ADVISORY, not of the casilla. "Art. 61 norma 1 halves this" is a claim about the
rule that produced the number; the casilla's refs describe what establishes the
box. Those coincide for one kind of advisory and diverge for the kind that
dominates here.

That divergence is invisible to every gate the project has. A mechanically
converted site would carry a resolving id, satisfy any structural check, and
state a provision one level too coarse to be the rule the operator was told
about. The gap between "a ref that resolves" and "the ref that governs" is
precisely the gap a precision defect lives in, and only an authoring decision
closes it.

The empty feared population is what makes option 1 affordable. Had the
provisions been absent from the catalogue, the work would have been legal
authoring under human review; because they are present, it is per-site
adjudication against entries that already exist.

## Consequences

**Gains.** An operator-facing regulatory claim becomes checkable for the first
time. A renumbered or retired provision reds at registry build instead of
surviving in a string. And the typed form stops being less precise than the
prose, which is the specific regression option 2 would have shipped.

**Difficulties.** Per-site adjudication does not parallelise into a sweep, and
the population-C modules need signature changes before they can carry anything.
The honest consequence is that this closes slowly.

**Pitfall guarded against.** The one grounded instance reads as a template and is
not one. A future author copying it onto an eligibility-rule advisory reproduces
exactly the defect this record rejects, which is why the two paths are
distinguished on the diagnostic rather than by convention.

**Unmeasured, stated rather than buried.** The twelve modules asserting no
provision were not re-read; nothing here says they are proper, only that nothing
contradicts it. And whether a given catalogue entry is the provision that
actually governs a given advisory is a tax review this record cannot pre-empt.
