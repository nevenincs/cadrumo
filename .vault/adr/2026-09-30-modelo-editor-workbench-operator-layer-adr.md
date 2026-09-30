---
tags:
  - '#adr'
  - '#modelo-editor-workbench'
date: '2026-09-30'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:31174af6eccf04c64612ba82e154a9970e2589e1f2b593db7190bd1ced01c9fe'
related:
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-09-30-modelo-editor-workbench-edit-interaction-research]]"
  - "[[2026-09-30-modelo-editor-workbench-imports-bindings-research]]"
  - "[[2026-09-30-modelo-editor-workbench-reference]]"
  - '[[2026-09-30-modelo-editor-workbench-journey-help-research]]'
---

# `modelo-editor-workbench` adr: `Persisted operator layer and replayed caller context` | (**status:** `accepted`)

## Problem Statement

A person who edits a declaration loses work. The edit executor builds its calculation inputs
from the submitted intents alone, and calculation is memoryless, so a second edit silently
returns every earlier manual value and binding override to its source value. The TUI Calculate
action submits no caller inputs at all and drops manual values, overrides and detail rows on
every recalculation. Every Modelo 303 edit fails because the executor omits the filing-instance
evidence the calculation requires. These were reproduced on real encrypted storage
(`2026-09-30-modelo-editor-workbench-edit-interaction-research`, bugs 4.1, 4.2 and 4.15) and
found independently (`2026-09-30-modelo-editor-workbench-imports-bindings-research`, B1 to B3).

The accepted edit contract already states that intent absence means unchanged
(`2026-08-24-modelo-edit-contract-adr`, D4). The executor cannot honour it, because a revision
does not record which of its inputs the operator authored: the persisted input and binding maps
merge every source tier. No editor can be trustworthy until that is decided, so this decision
precedes every editing surface in `2026-09-30-modelo-editor-workbench-adr`.

## Considerations

- The persisted `input_values_by_casilla_id` and `binding_overrides` merge declaration-period,
  backend, bound, profile, borrador and caller values, so replaying them would freeze source
  values as operator overrides that outrank every later source
  (`2026-09-30-modelo-editor-workbench-edit-interaction-research`, 1.3;
  `2026-09-30-modelo-editor-workbench-imports-bindings-research`, 1.3 and B9).
- The calculation boundary already receives the caller layer separately from the source tiers
  (`src/cadrumo/application/modelo/calculation_actions.py:1431`); it only fails to persist it.
- Optional revision identity keys are omitted when empty, so a new optional axis leaves every
  stored revision's content address unchanged
  (`src/cadrumo/domain/modelos/calculation_revision_identity.py:209`).
- Other caller-supplied, non-source inputs already live on the revision and must also reach the
  next calculation: detail rows, filing-instance evidence, the Modelo 210 fields and the borrador
  snapshot (`2026-09-30-modelo-editor-workbench-edit-interaction-research`, 2.6).
- The five-minute edit baseline is admitted once while the workbench composes and is keyed on
  whole-bucket catalogue digests, so any apply after five minutes, or after any other
  declaration in the profile recalculates, is refused
  (`2026-09-30-modelo-editor-workbench-edit-interaction-research`, 1.4).
- Override eligibility for seventeen of thirty-three source kinds is undeclared, and deciding it
  is tax policy rather than presentation
  (`2026-09-30-modelo-editor-workbench-imports-bindings-research`, 1.1 and B8).
- Boolean, date and year manual casillas raise raw errors today, localized decimals escape as
  raw exceptions, and a money-only value bound refuses legitimate ratios and decimals
  (`2026-09-30-modelo-editor-workbench-edit-interaction-research`, 4.3 and 4.4).

## Considered options

1. **Replay the merged input and binding maps as the next caller layer.** Rejected: it converts
   ledger, profile and borrador values into operator overrides, so new ledger data would never
   reach the declaration again. A silent under-declaration by construction.
2. **Reconstruct the operator layer by recalculating without caller inputs and diffing.**
   Rejected: fragile, costs a second calculation per edit, and still cannot tell an operator
   value equal to its source from a source value.
3. **Require the frontend to resubmit every earlier value on each edit.** Rejected: it makes the
   frontend the custodian of taxpayer values and contradicts the contract's absence rule.
4. **Persist the operator layer on the revision and replay the full caller context from the
   current head.** Chosen.

## Constraints

- Bound by the accepted edit contract's intent families and its absence-means-unchanged rule
  (`2026-08-24-modelo-edit-contract-adr`, D4), and by its whole-set detail-row replacement
  amendment.
- Bound by `no-silent-under-declaration`: a missing, cleared, zero and source value stay
  distinct, and an operator value that displaces a source value stays visible.
- Bound by `no-legacy-compatibility`: stored revisions are not rewritten; the new axis is
  forward-only and absent on them.
- Bound by `sensitive-financial-data-secure-storage-only`: the layer is persisted only inside the
  encrypted revision and never in receipts, events, journals or logs.
- The CLI `modelo work calculate` keeps its explicit full-specification semantics under this
  decision; changing it would change a documented command contract and its generated reference.

## Implementation

A revision gains a typed operator layer: the casilla values the operator set, split by value
channel, the binding overrides the operator set, and the casillas the operator explicitly
cleared. It is recorded when a revision is calculated from operator intents, participates in
the content address only when present, and is absent on revisions stored before it existed.
An absent layer is read as unknown, never as empty, and the first edit on such a revision says
so in its review instead of guessing.

One application helper owns the caller context of a revision: its operator layer, detail rows,
filing-instance evidence, Modelo 210 fields and borrador snapshot. The edit executor starts from
the current head's caller context and applies the submitted intents to it. A set replaces the
operator value and removes any clear. A clear removes the operator value and records an explicit
clear only when no source feeds the casilla; on a source-fed casilla it is refused in favour of a
restore. A remove-override or restore removes the operator value so the source tiers win again,
which is the whole implementation of the binding intent refused today. An address the
submission does not name keeps its operator value. The TUI Calculate operation replays the same
caller context, so recalculating after new ledger data keeps the operator's values.

The executor returns typed refusals for every value, channel and precondition failure instead of
raising, routes boolean inputs through the decimal channel, keeps date and year casillas
non-writable until the engine has a channel for them, and runs off the event loop. The wire
value bound applies only to money addresses. A typed application parser, with a value grammar
projected per writable address at admission, owns lexical entry for every frontend and is
re-applied by the executor, so a value that passes the parser passes the engine. The grammar
reads each locale's number marks, refuses ambiguous separators and never rounds.

Admission corrections accompany the layer. The baseline is admitted lazily when an edit session
starts and renewed silently at review and at submit when nothing but its issue and expiry times
changed. Its concurrency coordinates narrow to the edited work unit's record and its calculation
head, amending the whole-catalogue coordinates of the edit contract. Admission refuses rather
than raises for a revision below filing grade, and its refusal reaches the interface. Row-field
template casillas and casillas without an engine channel are projected non-writable with their
own reasons. Binding overrides stay writable for manual-input bindings and become writable for
the carry sources the precedence ladder already classifies; every other source kind stays
read-only, with its override policy shown as undecided, until a grounded decision classifies it.

## Rationale

Only a persisted operator layer lets the executor distinguish "the operator typed this" from
"a source produced this", and that distinction is exactly what absence-means-unchanged, restore,
clear and override disclosure all require. The alternatives either promote source values to
overrides, which is the under-declaration the project's rules forbid, or push custody of taxpayer
values into the frontend. The calculation boundary already separates the caller tier, and the
identity machinery already tolerates new optional axes, so the change is additive at the
persistence boundary and needs no migration of stored data.

## Consequences

- Edits accumulate as the contract always promised; Calculate stops discarding work; 303 edits
  can succeed; clear and restore become real, distinct actions.
- Revisions calculated with an operator layer hash differently from otherwise identical revisions
  without one. That is correct: a declaration computed with an operator override is a different
  filing basis.
- Revisions stored before this decision expose an unknown operator layer. The first edit on one
  asks the operator to confirm manual values rather than inferring them.
- The CLI and the TUI differ on recalculation semantics until a later decision aligns the CLI;
  the difference is stated in the CLI's own help, not hidden.
- Seventeen source kinds remain read-only in the editor until their override policy is grounded.
  That is visible to the operator as a decision not yet made, not as a silent lock.
- Date and year casillas stay read-only in the editor until the engine gains a channel for them,
  with the reason shown on the row.
