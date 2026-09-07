---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4676d0a7aa24d6d9561a3d636531f58ecebff5203d85de0783356a7528f0fa9a'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-06-05-calendar-filing-semantics-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-09-04-tui-architecture-authenticated-tui-visibility-adr]]"
---

# `tuimodelo` adr: `filing lifecycle, history and status surfacing` | (**status:** `proposed`)

## Problem Statement

The modelo declaration TUI must show an operator which declarations exist, what state each
is in, what is due, what was missed, and what may still be done to each one. No such
surface is reachable today: the filing-history zone is hardcoded unavailable and the AEAT
evidence axis is hardcoded as never captured, although the merge helper already exists
(`2026-09-07-tuimodelo-reference`).

A decision is needed now because the campaign brief proposes a single status vocabulary —
filed, amended, missed, projected — that the domain does not have and that the accepted
calendar-filing semantics forbid by name. Building history against the brief's vocabulary
would collapse two axes an accepted decision holds apart, and would put a word
(`projected`) with no filing meaning onto a filing-grade surface. Every later surface in
the campaign addresses work units by their lifecycle state, so the vocabulary must be
settled before the reachability, editor, verify and export waves can name their
preconditions.

## Considerations

- Local filing state and AEAT submission state are two independent axes held apart by four
  validators; a local "filed" must never imply AEAT received it
  (`2026-06-05-calendar-filing-semantics-adr`).
- Filing can never mean live submission: the access gate unconditionally refuses live
  writes and no submitter transport exists (`2026-09-07-tuimodelo-reference`).
- "Missed" exists only on calendar rows, not on the stored record, so any history surface
  must join two projections by natural address (`2026-09-07-tuimodelo-reference`).
- The work unit is content-addressed, so rename does not change identity, and discard is
  terminal with no undo (`2026-09-07-tuimodelo-reference`).
- A superseded revision must never render as current; a dedicated current-sealed state set
  exists for exactly this (`2026-09-07-tuimodelo-reference`).
- One history-shaped module in the application tree is dead code with an untyped status
  field, and is a trap for an implementer searching by name
  (`2026-09-07-tuimodelo-reference`).
- The modelo history command bypasses the application layer entirely and owns its event
  taxonomy and filtering policy inside the CLI handler, so no service exists for a second
  surface to call (`2026-09-07-tuimodelo-reference`).
- A blocker-to-operator-action projection with an import-time totality check already exists
  and answers "what do I do next" for all 21 cross-period blockers
  (`2026-09-07-tuimodelo-reference`).
- The host workspace for filing history is already decided: an accepted decision places history
  under Declarations, so this record adopts that placement rather than choosing one
  (`2026-09-02-unreachable-capability-tui-navigation-join-adr`).
- The action denominator classifies 13 work-family reads and six work-family mutations as
  pending, and reds immediately if a new command appears
  (`2026-09-07-tuimodelo-reference`).

## Considered options

1. **Adopt the brief's flat vocabulary (filed / amended / missed / projected).** Rejected:
   it collapses the two axes the accepted calendar semantics forbid collapsing, and
   `projected` names nothing in the domain.
2. **Surface the raw enums unchanged, one column per enum.** Rejected: the operator would
   read five separate state columns per row and would still have to join calendar rows to
   records mentally; it exports the domain's internal shape as the user interface.
3. **Invent a derived single status by precedence over the two axes.** Rejected: any
   precedence rule silently decides which axis wins, which is precisely the collapse the
   parent decision prohibits, and it destroys the distinction between "we filed and AEAT
   confirmed" and "we filed and never checked".
4. **Two-axis presentation joined to an obligation axis, with a separate next-action
   column.** Chosen: it preserves both governed axes, gets "missed" from the obligation
   axis where it actually lives, and answers the operator's real question through the
   existing blocker-to-action projection rather than through a status word.

## Constraints

- Blocked on the CLI-to-backend migration wave: no application service owns modelo history,
  so the surface cannot be built without first relocating that policy out of the CLI
  handler. This ADR does not authorise a second implementation in the frontend.
- Depends on the accepted calendar-filing semantics remaining in force; if that decision is
  ever superseded, the two-axis presentation must be revisited with it.
- Depends on the accepted modelo workspace interface decision for destination admission, which
  is accepted and unamended in the areas this record relies on.
- The action denominator enumerates this record's scope but does not yet prove admission: its
  drift check observes four mechanical signature fields and neither the recorded disposition
  nor the interface capability is among them. Extending it so that a delivered surface and its
  classification must agree is a prerequisite of this record, not a property it may assume.
- The retired exit-receipt family must not be reintroduced as a gating mechanism for these
  surfaces.
- A money column is deferred on a data ground only: the filing reference projection carries no
  monetary field and settled results are absent for at least two high-traffic modelos. It is
  not deferred on a redaction ground — the accepted authenticated-visibility decision retired
  that posture and ordered the affected projections re-derived, so an authenticated operator
  sees their own amounts in full once the projection carries them
  (`2026-09-04-tui-architecture-authenticated-tui-visibility-adr`).
- No live-write capability may be added, implied, or labelled by any surface this record
  governs.

## Implementation

History is presented as a joined projection assembled in the application layer, never in
the frontend. The join key is the natural filing address — bucket, modelo, filing year,
period and member identity — which is the only key both the stored record and the calendar
row share.

Three axes are carried through to presentation and never merged. The local filing axis
reports whether the product has produced and marked a filing. The AEAT submission axis
reports what, if anything, has been observed from the authority, up to a verified
justificante. The obligation axis reports the calendar position — upcoming, due soon, due
today, overdue, filed, or not applicable — and is the sole origin of the operator-facing
notion of a missed declaration. Where the brief said "projected", the surface shows the
obligation axis's upcoming state for a period that has no work unit yet; there is no
projected filing, only an unstarted obligation.

Revision state is displayed through the current-sealed state set so that a superseded
revision is visibly historical rather than current. Amendment rows disclose their kind and
the legal basis that governs it, because the three kinds carry materially different
operator consequences and one of them is refused outright when it would lower liability
before the rectificativa era.

Alongside the axes, each row carries a next-action cell derived from the existing
blocker-to-operator-action projection rather than from a status string. This is what makes
the surface actionable without inventing a workflow vocabulary.

Filing is presented honestly as a two-part act: the product produces the fichero and the
operator uploads it at the authority's site, after which the local record is marked and a
justificante may be observed and verified. No control on any surface may suggest that the
product transmits a declaration.

Discard is presented as terminal and is confirmed accordingly; rename is presented as
cosmetic because identity is content-addressed and does not move.

The dead history module in the application tree is deleted rather than left as a naming
trap, and the modelo history policy relocated out of the CLI becomes the single service
both surfaces call.

## Rationale

The knockout criterion is the accepted calendar-filing semantics: three of the four options
either collapse the two axes it protects or re-encode that collapse behind a derived word.
Only the two-axis presentation survives that constraint intact, and it does so without
inventing anything — every axis it shows already exists and is already validated, and the
next-action column is a projection the domain already computes with an import-time totality
check over all 21 blockers (`2026-09-07-tuimodelo-reference`).

The option also resolves the brief's vocabulary problem rather than papering over it.
"Missed" turns out to be an obligation fact, not a record fact, which is why it could never
be found on the record; reading it off the obligation axis is both correct and simpler than
the join the brief implied. "Projected" dissolves entirely into an unstarted obligation,
which removes a filing-grade word that would otherwise have had to be defined from nothing.

Choosing presentation-layer honesty over a single tidy status column costs a wider row and
buys the one property this domain cannot trade away: an operator can never mistake a local
mark for authority confirmation.

## Consequences

The surface becomes buildable as a wiring exercise: the merge helper, the obligation
engine, the blocker projection and the state sets all exist, and the two hardcoded
unavailability stubs are the only things standing between the operator and a populated
history.

The campaign inherits a hard prerequisite. Because modelo history has no application
service, the history surface cannot be delivered before the CLI migration wave completes.
That ordering is a benefit disguised as a cost: it converts a would-be duplicate
implementation into a shared one, and it gives the migration wave a concrete acceptance
test rather than an architectural argument.

Rows will be wider than a single-status design and will need care at narrow terminal
geometries, which the acceptance matrix already exercises across three widths. Operators
accustomed to a single status word will see two, and the interface must teach that
distinction through labelling rather than assume it.

A money column is deferred, and the reason matters because the obvious one is wrong. Nothing
about operator privacy withholds it: the accepted authenticated-visibility posture shows an
authenticated operator their own data in full. It is deferred because the projection carries no
monetary field and settled results are missing for at least two high-traffic modelos, so
promising a total now would either show blanks that read as zero or force a second computation
path. Both are refused. The column arrives when the projection carries the value, which is a
scheduled data change rather than a policy question.

Deleting the dead history module removes a trap but touches a module another campaign may
still reference by name, so the deletion is sequenced with the migration wave rather than
taken opportunistically.
