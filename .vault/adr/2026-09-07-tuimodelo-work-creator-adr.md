---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:c3bab1b5d072347e77dde92cc8d7ace25741813043e6a3bc72a072b0d6a992aa'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
---

# `tuimodelo` adr: `period-driven declaration creator` | (**status:** `proposed`)

## Problem Statement

An operator cannot start a declaration from the full-screen product. Work-unit creation is
the sole `DEFERRED` row in the modelo action denominator, and the governing workspace
interface decision explicitly withholds it from every cohort: the selection destination may
render its deferred capability and reopening facts, but no cohort invokes it
(`2026-08-24-tui-modelo-workspace-interface-adr`). A test currently holds that door shut by
design (`2026-09-07-tuimodelo-reference`).

That decision names the conditions for reopening, and this record exists to meet them. It
requires a later accepted decision defining absent-work admission, the domain capability and
enrolled operation behind it, the atomic work-unit and creation-event write set, an
authoritative result and effect receipt, and the dependency and interface proofs
(`2026-08-24-tui-modelo-workspace-interface-adr`).

Two of those five clauses name a receipt mechanism that a later accepted decision retired
outright, along with its schemas and validators (`2026-09-07-tuimodelo-reference`). This
record therefore cannot discharge the deferral by satisfying its literal text, and must say
what replaces the retired clauses rather than quietly ignoring them or rebuilding a
mechanism the project removed.

The decision is needed now because creation is the entry point to every other surface in the
campaign. Reachability, editing, verification, export and history all address a work unit
that something must first create, and today only a separate command-line process can do it.

## Considerations

- Creation is the single `DEFERRED` row among 79 classified action candidates, and the
  denominator reds immediately if a new command appears
  (`2026-09-07-tuimodelo-reference`).
- The reopening clause predates the retirement of the exit-receipt family, so two of its
  five required proofs name schemas that no longer exist
  (`2026-09-07-tuimodelo-reference`).
- The surviving admission mechanism is the action denominator, explicitly retained because
  it asserts implementation shape (`2026-09-07-tuimodelo-reference`).
- A modelo work wizard already exists in the application layer and renders as an ordinary
  flow screen, so guided creation needs no new frontend class
  (`2026-09-07-tuimodelo-reference`).
- Revision selection has a single resolver that fails closed in both directions, and a
  revision identifier is an assertion rather than a selector
  (`2026-09-07-tuimodelo-reference`).
- 91 of 149 modelo enum members have no registry definition and must refuse creation;
  54 revisions refuse a filing-grade snapshot (`2026-09-07-tuimodelo-reference`).
- Period legality is per modelo and per schedule, and at least one high-traffic modelo
  carries separate quarterly and monthly schedules
  (`2026-09-07-tuimodelo-reference`).
- Applicability for a period is already derivable from the taxpayer profile and the
  registry schedule, so "what must I file" is an answerable query rather than a new
  computation (`2026-09-07-tuimodelo-reference`).
- The work unit is content-addressed over its coordinates, so creation is idempotent in
  identity but not in effect, and discard is terminal with no undo
  (`2026-09-07-tuimodelo-reference`).
- Creation is a mutation, and every other frontend-triggered mutation enters through the
  operation registry and supervisor (`2026-09-07-tuimodelo-reference`).

## Considered options

1. **Leave creation deferred and require the command line to start work.** Rejected: it
   makes the full-screen product unusable standalone and forces a process switch at the
   entry point of every workflow.
2. **Offer a bare create form taking modelo, year and period.** Rejected: it pushes
   applicability, schedule legality and revision resolution onto the operator, and produces
   refusals after the fact for the 91 modelos with no definition.
3. **Drive creation directly from the frontend against the work-lifecycle boundary.**
   Rejected: creation would become the only mutation outside the supervisor, without
   journal, lease or cancellation.
4. **Period-first guided creation over the existing wizard, as an enrolled operation, with
   applicability filtering the offered set.** Chosen: it starts from the question the
   operator actually has, reuses the existing flow substrate and wizard definition, refuses
   impossible coordinates before asking rather than after, and keeps creation inside the
   same governance as every other mutation.

## Constraints

- Two of the five reopening clauses are undischargeable as written because the receipt
  family they name was retired. This record substitutes the surviving denominator and the
  operation registry's own result contract; it does not reconstruct the retired schemas.
- Creation cannot be surfaced before it is enrolled as an operation, which is the same
  prerequisite the import wave carries.
- Depends on the accepted workspace interface decision, which owns destination admission
  and the cohort model, and which is stable in the areas relied on here.
- Depends on the registry authority's revision resolver; no surface may select a revision by
  identifier, ordering or recency.
- The deferred-creation sweep test must be retired atomically with the reopening, not left
  asserting a door that has opened.
- Creation must not imply a filing obligation exists where the profile does not establish
  one, and must not offer modelos the registry cannot support.
- No live-write capability is introduced; creating a declaration is a purely local act.

## Implementation

Creation is period-first. The operator names the period they are working on, and the product
answers with the declarations that period actually implies for this taxpayer, derived from
the profile and the registry schedules rather than from a static list. Each offered
declaration carries its own admissibility: whether the registry defines it, whether the
resolved revision supports a filing-grade result, and whether work already exists for those
coordinates.

Absent-work admission is defined as the state where the profile and registry establish an
applicable declaration for a period, the registry resolves exactly one revision for it, and
no live work unit holds those coordinates. Admission is a read, computed before anything is
offered, so the operator is never shown a choice that will be refused when taken. Where a
discarded work unit already holds the coordinates, the surface states that creation is
refused and why, because discard is terminal and re-creation is not the recovery path.

Revision resolution stays with the single resolver. The surface displays the revision that
the law and the filing context select, and offers no way to choose another. A modelo whose
period cannot resolve a revision, or resolves ambiguously, is presented as unavailable with
the resolver's own reason rather than defaulted.

Creation is an enrolled operation, so it inherits journalling, leasing, cancellation and the
supervisor's result contract like every other mutation. Its write set is atomic across the
work unit and its creation event: either both land or neither does. The operation's own
typed result is the authoritative record of what happened, and it is what the surface
renders on completion; this replaces the retired result-receipt clause of the reopening
requirement.

Admission proof is the action denominator. Creation moves from the deferred disposition to
an enrolled one in the same change that enrols the operation, and the denominator gate fails
until the classification and the live shape agree. This replaces the retired dependency and
interface receipt clauses: the proof that creation is properly admitted is that the standing
gate accepts its new classification, not that a bespoke receipt schema was authored.

Presentation reuses the existing wizard definition through the ordinary flow renderer. No
new full-screen class is introduced for the creator itself, which keeps it inside the
already-enrolled flow ownership rather than adding a destination to a closed catalogue.

The sweep test that currently holds creation shut is retired in the same change that opens
it, so the repository never contains both an open door and a test asserting it is closed.

## Rationale

The chosen option wins on the question it starts from. An operator does not think "create a
modelo 303 work unit for 2026-2T"; they think "it is April, what do I owe". Period-first
creation answers that directly, and in doing so it filters out the two largest sources of
downstream refusal — undefined modelos and unresolvable revisions — before the operator
commits to anything. The bare form defers exactly those refusals to after the choice, which
is the worst place for them.

Reusing the existing wizard and flow substrate is what keeps this cheap. The definition and
the renderer both exist; what is missing is enrolment and an applicability-filtered entry,
not a user interface.

Routing creation through the operation registry is the same argument that governs import in
the sibling record: creation is a mutation, every other mutation is supervised, and the one
exception would be the one without cancellation or a journal.

The substitution for the retired clauses is the part of this record that most needs to be
explicit. The reopening requirement asked for proofs in a currency the project has since
withdrawn. Honouring its intent means asking what the retired receipts were for —
demonstrating that a capability is admitted deliberately rather than by accident — and
supplying the mechanism the project kept for exactly that purpose. Rebuilding the receipts
would contradict an accepted decision and repeat a failure the corresponding audit
identified by name.

## Consequences

The product becomes usable without a second process at its entry point, which is the single
largest usability gain in the campaign and a precondition for demonstrating any other
surface end to end.

The creator will refuse more often than a naive form would, and visibly so: 91 modelos have
no registry definition, 54 revisions cannot produce a filing-grade result, and discarded
coordinates cannot be reused. Those refusals are correct and are better surfaced at the
point of choice, but they will make the offered set look narrow, and the copy must explain
narrowness rather than merely enforce it.

Enrolling creation as an operation is backend work that gates the surface and touches a
registry other campaigns extend, so it needs the same single-writer coordination as the
import enrolment.

Discharging the deferral on substituted terms is a governance judgement, not a mechanical
step. This record should be read with attention on that point during verification: if the
substitution is wrong, the correct remedy is to amend the parent decision's reopening
clause rather than to resurrect the retired receipts.

Retiring the sweep test removes a guard that has been holding a real invariant. Its
replacement is the denominator classification, which is stronger, but the change must land
atomically or the repository briefly asserts two contradictory things.
