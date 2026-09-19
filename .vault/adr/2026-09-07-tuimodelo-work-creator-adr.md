---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:95eb67e77393eadb822b9a6d3316cb7f549a21e3e03f160692421886d85ae3ee'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-09-07-tuimodelo-satellite-families-adr]]"
  - "[[2026-09-07-tuimodelo-adapter-migration-adr]]"
---

# `tuimodelo` adr: `period-driven declaration creator` | (**status:** `accepted`)

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

Two receipt families must be kept apart here, because conflating them is the easiest way to
get this record wrong. The interface exit-receipt family was retired outright along with its
schemas and validators. The edit-contract mutation result receipt was not: it is live,
persisted encrypted, and accepted `2026-08-24-modelo-edit-contract-adr` requires every
lifecycle mutation to declare both an atomic write set and a result receipt
(`2026-09-07-tuimodelo-reference`). So one of the five clauses is undischargeable as written
and one is a live obligation this record must meet rather than replace.

The parent decision has also already spoken. Its 2026-08-28 amendment performed the
interface-proof substitution and names the work-creation paragraph verbatim
(`2026-08-24-tui-modelo-workspace-interface-adr`). This record adopts that amendment rather
than re-deciding it.

The decision is needed now because creation is the entry point to every other surface in the
campaign. Reachability, editing, verification, export and history all address a work unit
that something must first create, and today only a separate command-line process can do it.

## Considerations

- Creation is the single deferred row among 79 classified action candidates
  (`2026-09-07-tuimodelo-reference`).
- The action denominator as it stands is a scope enumerator, not an admission gate: its drift
  check compares only four mechanical signature fields, and neither the recorded disposition
  nor the observed interface capability is among them, so wiring a surface reds nothing. Its
  closed taxonomy also has no arm a delivered mutation can move to
  (`2026-09-07-tuimodelo-reference`).
- The interface exit-receipt family is retired and rebuilding it is a named hazard; the
  edit-contract mutation result receipt is live and required of lifecycle mutations
  (`2026-09-07-tuimodelo-reference`).
- The parent's 2026-08-28 amendment already substituted the interface proofs, and requires
  both an execution record and a green conformance suite — not one or the other
  (`2026-08-24-tui-modelo-workspace-interface-adr`).
- Period-first creation already exists in the product as the calendar recovery action, so
  this record governs an existing affordance rather than introducing one
  (`2026-09-07-tuimodelo-reference`).
- A modelo work wizard already exists in the application layer and renders as an ordinary
  flow screen, so guided creation needs no new frontend class
  (`2026-09-07-tuimodelo-reference`).
- Revision selection has a single resolver that fails closed in both directions, and a
  revision identifier is an assertion rather than a selector
  (`2026-09-07-tuimodelo-reference`).
- 91 of 149 modelo enum members have no registry definition and must refuse creation;
  59 revisions refuse a filing-grade snapshot (`2026-09-07-tuimodelo-reference`).
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

- The interface-proof clause is discharged by adopting the parent's 2026-08-28 amendment in
  full, including both halves it requires. The retired exit-receipt schemas are not
  reconstructed.
- The result-receipt clause is a live obligation, not a retired one. Creation declares its own
  result receipt under the edit contract's existing pattern; the supervisor's in-memory result
  is not a substitute, because it does not survive the crash the receipt exists to prove
  against. Amending that obligation would require amending the edit-contract decision openly.
- The admission gate this record relies on does not yet exist in enforceable form. Extending
  the denominator to observe interface capability and dispatchability, to carry a delivered
  arm, and to red on a disposition that contradicts the observed shape is a prerequisite, not
  an assumption.
- Creation cannot be surfaced before it is enrolled as an operation, which is the same
  prerequisite the import wave carries.
- The capability projection and the parent's mapped-result-destination conjunct apply to
  creation and must be satisfied, not merely cited.
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

Creation is an enrolled operation, so it inherits journalling, leasing and cancellation like
every other mutation. Its write set is atomic across the work unit and its creation event:
either both land or neither does.

Creation declares its own result receipt under the edit contract's existing pattern, persisted
through the same encrypted boundary as other mutation receipts. The supervisor's typed result
is what the surface renders on completion, but it is not the durable record: it does not
survive the crash the receipt exists to prove against, and the accepted edit-contract decision
requires an atomic write set and a result receipt together. Both are declared here.

Interface proof follows the parent's 2026-08-28 amendment as written, which means both halves
it requires: an execution record and a green conformance suite. Neither alone discharges it.

Admission proof is the extended action denominator. Creation moves from the deferred
disposition to a delivered one in the same change that enrols the operation and wires the
surface, and the gate reds while the recorded disposition and the observed shape disagree.
That gate does not exist yet in enforceable form, and extending it is a prerequisite of this
record rather than a property it may assume.

Presentation reuses the existing wizard definition through the ordinary flow renderer, and
governs the period-first creation affordance the calendar already offers as a recovery action
rather than introducing a parallel one. No new full-screen class is introduced, which keeps
creation inside the already-enrolled flow ownership rather than adding a destination to a
closed catalogue.

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

The receipt question is the part of this record that most needs to be explicit, because the
tempting answer is wrong in both directions. Treating every receipt as retired would discard a
live obligation and the crash proof it exists to give; treating every clause as binding would
rebuild schemas an accepted decision removed and repeat a failure the corresponding audit
named. The record therefore splits them: the interface proof follows the parent's own
amendment, and the result receipt is declared under the pattern that is still in force and
still persisted.

The admission argument is stated as a prerequisite rather than a claim for the same reason.
It would be easy to assert that the standing denominator proves admission; it does not, because
its drift check never observes the disposition or the interface capability. Saying so, and
scheduling the extension that makes it true, is the difference between a decision that can be
verified and one that merely reads as if it could.

## Consequences

The product becomes usable without a second process at its entry point, which is the single
largest usability gain in the campaign and a precondition for demonstrating any other
surface end to end.

The creator will refuse more often than a naive form would, and visibly so: 91 modelos have
no registry definition, 59 revisions cannot produce a filing-grade result, and discarded
coordinates cannot be reused. Those refusals are correct and are better surfaced at the
point of choice, but they will make the offered set look narrow, and the copy must explain
narrowness rather than merely enforce it.

Enrolling creation as an operation is backend work that gates the surface and touches a
registry other campaigns extend, so it needs the same single-writer coordination as the
import enrolment.

The campaign inherits the denominator extension. Creation cannot be admitted provably until the
gate observes interface capability and dispatchability and carries an arm a delivered mutation
can occupy, and that module is claimed by another campaign's open row, so it needs single-writer
coordination before either touches it.

Retiring the deferred-creation guard is not the single test edit it first appears to be. The
door is held by several tests plus an allowlist plus a denominator assertion, and some of those
assert invariants that should survive the reopening. Each must be adjudicated individually, and
the reopening must land atomically with them or the repository briefly asserts two contradictory
things.

Governing an affordance that already exists carries its own risk: the calendar's recovery action
must be brought under this decision rather than left as a second path, or the product will have
two ways to create work with one of them ungoverned.
