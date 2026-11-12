---
tags:
  - '#adr'
  - '#prior-carry-attestation'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:2f67cc6c2ad392b7f29ced73e602f36d6e1087f06e36ff2d33cabd3b30a28a8e'
related:
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - '[[2026-11-08-prior-carry-attestation-reference]]'
---

# `prior-carry-attestation` adr: `withdrawing a carry statement returns the work unit to no calculation` | (**status:** `accepted`)

## Problem Statement

`2026-11-08-prior-carry-attestation-adr` says `REMOVE_OVERRIDE` on an attested carry withdraws the statement, but a withdrawal of the `renta_negative_general_bases_pending` family is refused on a real Modelo 100, one member or all four. Before the statement no calculation revision existed: calculate refuses an unstated carry before publication (`src/cadrumo/application/modelo/calculation_actions.py:946`, `src/cadrumo/application/modelo/work_missing_input.py:200`), the statement lives only on a revision's operator layer (`src/cadrumo/application/modelo/caller_context.py:74`), and the work unit's current-calculation pointer only moves forward (`src/cadrumo/application/modelo/revision_persistence.py:208`, `:352`; `src/cadrumo/application/modelo/amendment_actions.py:1091`). The edit therefore recalculates, the recalculation refuses, and the operator gets a refusal with no reason. The coordinator ruled on 2026-11-12 that a statement must be withdrawable, so the return to the pre-statement state needs a stored form.

## Considerations

- An unstated carry stays refused at calculation; absence is never inferred (the accepted record above).
- The pointer may already be empty (`src/cadrumo/domain/modelos/work_unit.py:235`), so "no calculation" is a state the store already holds.
- Typed operator values are never discarded silently.
- A locally filed (`PRESENTADO`) revision is corrected only by amendment.
- The backend serves every word, including the reason a withdrawal is refused.

## Considered options

- A. Clear the current-calculation pointer when the head holds nothing but carry-family statements: restores the exact pre-statement state with no new record. Chosen.
- B. As A, keeping the other operator answers in a separate pending-answers record: a new persisted record; not started.
- C. Publish a revision with the carry unresolved so verification blocks: rejected, because a plain recalculation of the same inputs refuses while the edit would publish.

## Constraints

- Coordinator ruling of 2026-11-12 10:39 (the authorization sought for this amendment): option A, limited as below; not C; B not started.
- Amends the Implementation bullet "`SET_OVERRIDE_VALUE` and `REMOVE_OVERRIDE` on that binding withdraw the attestation" of `2026-11-08-prior-carry-attestation-adr` for the case where the withdrawal leaves the carry unstated.
- Revisions are never deleted; the withdrawn revision stays stored for audit.
- Accepted 2026-11-12 10:45 by CADRUMO-PRIME under the operator's delegation, as written. Conditions of acceptance: every reader of the current-calculation pointer that assumed it never returns to none (workbench form, overview and readiness, verification, export approval, amendment) is listed and tested, and none shows the withdrawn revision as current; approval and export evidence of the withdrawn revision are no longer current afterwards and nothing is deleted; proof runs through the real edit executor for every Modelo 100 year the envelope admits, including both refused cases.

## Implementation

We will let a withdrawal-only edit of a carry family move the work unit's current-calculation pointer back to none when, and only when, the head's operator layer holds nothing but statements of carry families.

- One member is the whole family: withdrawing any member withdraws the family's statement.
- The pointer move is compare-and-swap guarded against the baseline head and journaled through the ordinary operation and effect accounting. Afterwards calculate refuses as before the statement, with the attest door, and the form offers the statement again.
- A head holding any other operator value refuses the withdrawal with served words naming what would be lost and the door to replace the statement with the figure; typed values are never discarded.
- A `PRESENTADO` head refuses with the amend door.
- The edit preview serves the effect words: the calculation is withdrawn and runs again after the carry is stated.
- An edit refused for an unstated carry serves the public fact code `REFUSED_MODELO_PRIOR_CARRY_ABSENCE_UNSTATED` and the `operator.modelo.work.attest_prior_carries` door; amounts stay stripped.
- Evidence: the real edit executor and stores, for every Modelo 100 year the registry envelope admits.

## Rationale

Option A restores the one state the system already defines for "nothing stated" without a new record or an exception to the calculation refusal, and its limits keep every typed value and every filed revision out of its reach.

## Consequences

- The current-calculation pointer gains one backward move, limited to this case; readers that assumed a monotonic pointer must accept none after a withdrawal.
- A filer who stated the carries and also typed other values must replace the statement with a figure rather than withdraw it, until option B is decided.
- Families whose unstated state still calculates (work income, relation carries, the Modelo 130 stated figure) keep withdrawing through an ordinary recalculation.
