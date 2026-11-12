---
tags:
  - '#adr'
  - '#frontend-operator-statements'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:65c1356f0391da05f982c6fd89db71949c405d0fc3ff58b7eb1775c3d907534b'
related:
  - "[[2026-11-12-frontend-refusal-ways-out-adr]]"
  - "[[2026-11-03-backend-served-surface-adr]]"
  - "[[2026-10-23-desktop-modelo-workspace-adr]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-11-02-desktop-renta-adr]]"
  - '[[2026-11-12-frontend-operator-statements-reference]]'
  - '[[2026-11-08-prior-carry-attestation-adr]]'
  - '[[2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr]]'
---

# `frontend-operator-statements` adr: `One statement pattern per frontend for attest-no-amount, attest-prior-value and absence by family` | (**status:** `proposed`)

## Problem Statement

The backend now takes operator statements as first-class edit intents: `attest_no_amount` on one binding, `attest_prior_value` on one binding naming the earlier return it stands in for (`2026-11-11-cross-period-filing-clean-state-out-of-envelope-attestation-adr`), and a per-family statement of absence served as `carry_attestations` on the form (`2026-11-08-prior-carry-attestation-adr`), whose families grow (two on the wire, a per-property-row family accepted). The window has one banner written for one family and never reads the edit surface's `allowed_intents`; the TUI has no statement at all. Evidence: `2026-11-12-frontend-operator-statements-reference`.

## Considerations

- Statements are served: `allowed_intents` per binding (`src/cadrumo/application/modelo/edit_admission.py:251`), `carry_attestations` with `action_words`, `statement_words` and `effect_words` per family, and `stated_absent` per form field.
- No words are served yet for a per-binding statement (what it states, its effect, the return it stands in for), and the form marks no field as a stated prior value.
- A stated zero must never read as a typed zero, and an unstated value never as zero (`2026-11-08-prior-carry-attestation-adr`; the proposed `2026-11-02-casilla-value-absence-adr` points the same way).
- Families grow: per declaration today, per property row next, one statement covering every open family later.

## Considered options

- Extend the window's one-family banner per family. Rejected: a one-member union per family is the drift the frontend survey found.
- One statement model per frontend over served data, offered where the backend admits it (chosen).
- Statements outside the edit session as their own operations. Rejected: the backend applies them as edit intents through ordinary review and withdraws them with the ordinary intents.

## Constraints

- A statement is offered only where served: a family statement from `carry_attestations`, a per-binding statement only where `allowed_intents` holds the intent. A frontend never decides that a box can be stated.
- Every word is served: the action, what is stated, its effect, and for a prior value the return it stands in for. A per-binding statement without served words is not offered; the gap is a backend ask.
- A field shows three distinct states from served data: unstated, typed, stated. A stated field shows the served origin words and its statement; it is never styled as a typed value.
- Families are iterated, never switched on: no frontend type, branch or key names a family. A row-scoped family renders on its row.
- Statements stage as edit intents and apply through the existing review; withdrawal stages `remove_override` on the same address and is offered on every stated field, labelled by a generic chrome key.
- Statement-based figures that verification or export disclose (`cross_period_dependency_operator_attested`, the export disclosures) render as served limitations, never as blockers; the refusal component of `2026-11-12-frontend-refusal-ways-out-adr` renders any refusal of a statement.

## Implementation

We will add one statement pattern per frontend.

- Window: a statement offer (family or binding scope, served words, the intents it stages) and a stated-field rendering in the form, replacing the one-family banner; `session.ts` stages and withdraws through its existing intent path; `stagedWords.ts` and the review dialog handle every intent kind of the generated union. Stories: family offer, per-binding no-amount, per-binding prior value with its source, stated field, withdrawal staged, row-scoped family, two families at once, no words served.
- TUI: the Modelo workbench editor offers the same statements on the selected field and on the form, with the same three field states.
- Backend asks (routed by PRIME): served words for per-binding `attest_no_amount` and `attest_prior_value` (action, statement, effect, the return stood in for), and a form-field marker for a stated prior value beside `stated_absent`.
- Hypothesis: component names and the exact placement in the form.

## Rationale

The backend already decides where a statement is admissible and serves the family words; a generic pattern over that data takes the next family with no frontend change and keeps tax wording out of both frontends.

## Consequences

- The window's family banner is replaced by the general pattern; per-binding statements appear only once their words are served.
- The TUI gains statements for the first time.
- Reconsider if the backend moves statements out of the edit session.
