---
tags:
  - '#plan'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-26'
tier: L1
related:
  - '[[2026-07-24-evidence-revision-identity-adr]]'
  - '[[2026-07-25-evidence-revision-identity-operator-walkthrough-audit]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `evidence-revision-identity` plan

- [x] `S01` - Refuse a DESCARTADO unit in create_work_unit with an instructive message naming its state and a real next step, in the WorkUnitMutationRefusedError shape the same module already uses eleven lines below, rather than returning the discarded unit and letting every downstream verb deny it exists; `src/cadrumo/application/modelo/_work_lifecycle.py`.
- [x] `S02` - Gate that a discarded unit refuses at create and that the refusal names its state, closing the asymmetry where list_work_units hides a discarded unit by default while create_work_unit hands it back; `src/cadrumo/application/modelo/tests/`.
- [ ] `S03` - BLOCKED ON OPERATOR, the supersede transition as specified cannot be built, it carries the same inputs so it re-derives the id it is escaping and hits the amendment path's existing no-op refusal, and the escape requires a discriminator inside revision identity which this ADR reserves for operator sign-off; `see the supersede-implementation-findings audit, no source change`.
- [ ] `S04` - SUPERSEDED BY S08, the idempotence guard was scoped to a supersede verb that is no longer the recommended mechanism; `no source change`.
- [ ] `S05` - SUPERSEDED BY S08, the supersession event was scoped to a new verb, and PRESENTADO_SUPERSEDIDO already models supersession for the filed case across roughly a dozen surfaces; `no source change`.
- [ ] `S06` - BLOCKED ON S03 OR S08, a refusal cannot name a recovery verb until one exists; `src/cadrumo/application/modelo/_export.py, src/cadrumo/locales/`.
- [ ] `S07` - Convert the 72 directly-runnable display-only sequence frames weighted to the export and local filing verbs, and record why each of the 96 genuinely blocked frames cannot execute so display-only becomes a stated constraint rather than an unexamined default that hides the next dead end; `docs/_sequences/`.
- [ ] `S08` - BLOCKED ON OPERATOR, the source-issue route needs CalculationSourceIssue's closed reason Literal widened and its required binding_source relaxed on a strict-frozen persisted model verification reads, and that carrier means an observation no binding consumed, which misdescribes a deductible row that was consumed but lacks evidence; `see the supersede-implementation-findings audit, no source change`.
- [ ] `S09` - OPERATOR DECISION, choose among the three bounded options for dissolving the evidence trap, a discriminator inside revision identity, a new persisted issue envelope with its own roundtrip obligations, or widening an existing persisted model in a way that misdescribes the condition, since no cheaper fourth route exists; `operator decision, governing ADR constraint`.
## Description

Executes the accepted evidence-revision-identity decision, whose two halves have
different blast radii and are deliberately ordered rather than bundled.

S01 and S02 close the stranded filing target and go first. Work-unit creation
returns a discarded unit with no state check, so an operator following the obvious
instinct to discard and retry loses that filing target permanently, and every
downstream verb then refuses with the command that just ran. The fix is enrolment
under a refusal shape the same module already carries a few lines away.

S03 through S06 add the supersede transition: a named, non-destructive path
opening a new draft from a finalized revision and re-capturing the evidence bundle
at the next verify. Folding evidence into the revision id was rejected — it
reverses a published content-addressing invariant, moves every revision id in the
repository, and is the class of filing-grade change the decision reserves for
operator sign-off.

S07 addresses the structural reason the dead end shipped undetected: the docs gate
stops exactly where the refusals live.

## Steps

S01 and S02 close the stranded filing target. S03 through S06 add the supersede
transition and surface it in the refusals. S07 converts the display-only sequence
frames that made the dead end undetectable.

## Parallelization

S01 and S02 go first and do not wait on anything else in this plan. They are the
sharper defect, they are reachable by instinct rather than by a specific sequence,
and holding them behind a new lifecycle transition would keep a one-way trap open
for the duration of the larger change.

S03 through S05 are one coherent change — the transition, its idempotence guard
and its audit event belong in the same commit, since a transition that lands
without its guard is a creating mutation that double-writes on retry. S06 follows
S03 because a refusal cannot name a verb that does not exist yet, and it touches
the locale catalogue, which must be maintained through the locales CLI rather than
by editing the catalogue files.

S07 is fully independent, touches only the sequence contracts, and can be taken by
a separate owner in parallel with everything above.

## Verification

S01 is verified by S02 and not by inspection: a discarded unit must refuse at
create, and the refusal must name its state. Assert structure and the error type,
never the localised prose. The gate should also pin that the refusal is not
circular — the failure being corrected is a message that names the command the
operator just ran.

The supersede transition is a creating mutation, so it owes an idempotence proof:
a retry under the same key resolves to the existing successor with no second draft
minted and no duplicate lifecycle event, and its derived id must be clock-free so
a retry at a different instant resolves to the same record.

The frozen-bundle guarantee must be shown intact. The original finalized revision
stays readable and unmodified across a supersession — that immutability is the
reason this option was chosen over refreshing the bundle in place, so a test that
does not check it leaves the decision unverified.

For S07, a converted frame counts only if it executes the real chain. The finding
being addressed is that display-only frames make a dead end undetectable by
construction, so a conversion that leaves the export or filing verb unexecuted has
reproduced the defect rather than fixed it.
