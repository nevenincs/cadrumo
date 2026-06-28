---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - "[[2026-05-21-persona-fleet-round2-findings-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-21-state-read-projection-adr]]"
  - '[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]'
---
# `cli-workflow-redesign` adr: `work verify validates a calculation and is independent of the filing-window deadline` | (**status:** `accepted`)

## Problem Statement

`aeat app modelo work verify <calculation_revision_id>` refuses with
`abort_code: NO_PENDING_OBLIGATION` whenever the deadline engine sees
no open filing window for the work unit's period. Four independent
testimonial personas (Inés, Pau, Lucía, Rosario - see
`[[2026-05-21-persona-fleet-round2-findings]]`) hit this after a
correct `work calculate`:

- The operator has calculated their modelo (130 / 303 / 100) and wants
  to verify the result is sound.
- `aeat app modelo readiness` for the same modelo reports
  `ready: True`.
- `work verify` refuses with `NO_PENDING_OBLIGATION` and offers no
  operator path forward.

`readiness: True` beside `verify: NO_PENDING_OBLIGATION` is a direct
cross-surface contradiction. In practice the deadline gate makes
`work verify` usable only inside an open AEAT filing window, so an
operator preparing a return early, or reviewing a past period, or
working offline cannot verify their own calculation at all.

## Considerations

- **Verification and filing are different acts.** `work verify`
  checks that a *calculation* is internally sound and matches the
  registry's verification expectations. Whether the AEAT filing
  *window* is open is a property of the calendar, not of the
  calculation. Coupling the two means a correct calculation cannot be
  confirmed correct just because it is the wrong week of the year.
- **The deadline gate has a correct home.** `NO_PENDING_OBLIGATION`
  is a meaningful refusal for the *filing* step (`work file`) and for
  the end-to-end automated pipeline (`work resume` / `WorkflowEngine`
  run): you should not file when there is no obligation. It is not
  meaningful for `verify`.
- **The state machine already separates the stages.** A revision
  moves `borrador -> VERIFICADO_COMPLETO -> filed`. `verify` performs
  the first transition; `file` performs the second. Only `file`
  needs the obligation to exist.
- **No live AEAT call is involved.** Verification is a local,
  registry-grounded check. Gating it on an obligation the operator
  cannot create offline strands the whole workflow with no recourse.
- **Pre-calculation is a first-class use case (owner-confirmed).**
  The project owner confirmed that calculations are normally done
  once a filing window opens, but that operators legitimately want to
  *pre-calculate ahead of time*: pre-calculating the Renta to estimate
  the year-end payment burden, and pre-calculating IVA modelos to know
  upcoming amounts due. Pre-calculation is, by definition, work done
  before the filing window opens - so verification of a pre-calculated
  modelo must not require an open window.

## Constraints

- `work verify` MUST remain a real verification - it still validates
  the calculation against the registry verification expectations and
  still refuses an unsound calculation. This ADR removes only the
  *deadline* precondition, not the verification itself.
- `work file` MUST keep the `NO_PENDING_OBLIGATION` guard - filing
  without an obligation stays refused.
- No live AEAT submission path is introduced (the safety-legal gate
  is untouched).
- Per the apex CLI ADR, no new root verbs.

## Decision / Implementation

1. `work verify` becomes **deadline-independent**. Its workflow path
   no longer runs the `COMPUTING_DEADLINES` stage as an abort gate;
   it verifies the calculation revision regardless of filing-window
   state.
2. The `NO_PENDING_OBLIGATION` gate stays on the **filing** path
   (`work file` and the end-to-end `WorkflowEngine` run) - filing
   still requires a pending obligation.
3. If the obligation/deadline context is genuinely useful on a verify
   result, it is surfaced as **informational** (e.g. "filing window
   opens YYYY-MM-DD"), never as an abort.
4. `modelo readiness` and `work verify` must agree: if `readiness`
   says a modelo is ready, `verify` must be reachable. After this
   change they no longer contradict.

`_stage_computing_deadlines` in `WorkflowEngine` carries concurrent
foreign WIP; the implementation must be sequenced carefully against
that and is tracked as a follow-up, not an ad-hoc patch.

## Rationale

Verifying a calculation is an act of checking correctness; it has no
honest dependency on the AEAT calendar. Tying the two produced a
contradiction four separate operators hit immediately, and made the
`borrador -> VERIFICADO_COMPLETO` transition unreachable for ordinary
offline preparation - the single most common way a taxpayer would use
this tool. Moving the deadline gate to the step where it is actually
meaningful (`file`) restores the workflow without weakening either
verification or the no-file-without-obligation safety property.

## Consequences

- The four-persona `work verify` blocker is resolved; `readiness` and
  `verify` stop contradicting each other.
- Offline / early / past-period preparation can reach
  `VERIFICADO_COMPLETO`.
- `work file` is unchanged - the obligation guard still protects it.
- The `WorkflowEngine` deadline-stage wiring changes; because that
  engine carries concurrent foreign WIP, the change is sequenced as a
  tracked follow-up rather than an immediate patch.
- **Owner decision (2026-05-21): accepted.** The project owner
  confirmed pre-calculation (Renta year-end-burden estimation, IVA
  upcoming-amounts) as a first-class use case, which this decision
  enables. Implementation is sequenced behind the in-flight
  modelo/bindings remediation (it shares `_modelo.py`) and around the
  `WorkflowEngine` foreign WIP.
