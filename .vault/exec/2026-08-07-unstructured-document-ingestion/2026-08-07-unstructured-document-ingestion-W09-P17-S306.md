---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:99b5a9160cddd47b81085f480a34e32b9a56da55e46059da6c411b760d1c21a4'
step_id: 'S306'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Correct the infectious claim about the M720 advisory

## Scope

- `src/cadrumo/application/calculations/tests`

## Description

- Replace the false claim with what is true, rather than deleting the paragraph.
- Name what IS unwired, so the correction leaves a reader better oriented than silence would.
- Record that the boundary is deliberate, because an absence reported as an accident and the same absence reported as a choice call for different actions.
- Change no code. The diff is prose only, confirmed by class rather than by reading: zero changed lines match an assertion, a definition, an import or an assignment.

## Outcome

The docstring asserted that the re-declaration advisory has no production caller and that verification never invokes it. Both halves are false. The trigger is reached on the verification path through the application-layer gate, which resolves the law-determined revision and folds the evidence, prior-baseline and declaration observations before calling it.

What is actually unwired is the advisory's INPUT. The single production calculate entry takes an input bundle carrying no observation field of any kind, so the resolver always runs with an empty collection, the revision's row bindings carry no asset rows, and the gate returns at its own evidence guard.

**And the boundary is deliberate rather than missing**, which the replacement says explicitly: the campaign that enrolled the resolver recorded that it did not approve a durable observation store, and the explicit observations parameter is the injection point left for one. The same absence reported as an accident reads as a defect and invites a fix; reported as a choice it reads as unfinished infrastructure and invites a ruling. Only one of those is true.

**This sentence is why the correction was worth a row.** It is infectious. This lane read it, believed it, and reported it upward as a finding before measuring anything — a wrong claim reasoned into is one author's error, while a wrong claim inherited from a docstring arrives pre-credentialed and launders itself through every reader who repeats it. The replacement therefore ends by pointing at the supply and saying the wiring question is settled, so the next reader does not re-derive it.

**What this excludes.** It corrects prose. It supplies no observation, changes no behaviour, and rules on nothing. Whether an operator should be told that a guard is dormant remains open and is not this row's to answer.

## Verification

Prose-only, and checked by line class rather than narratively:

    changed lines matching assert / def / import / assignment:  0

No gate run requested: no executable line changed, and the module's tests are untouched.

## Notes

**The artefact-contract distinction this row rests on, stated because it cuts against a precedent this campaign set earlier the same day.** A false claim surviving in a historical execution record is NOT rewritten: that record states what was believed when it was written, and the campaign's ability to distinguish delivered from delivered-narrower depends on those accounts staying fixed. A test module is source. Its prose is read as current, acted upon, and in this case propagated a wrong finding upward. Different artefacts, different contracts, and the record convention must not be applied to source.

The correction was rowed rather than made silently for the same reason the original claim did damage: a change to a statement that other people have been believing deserves to be findable.
