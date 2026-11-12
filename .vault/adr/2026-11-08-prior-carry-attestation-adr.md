---
tags:
  - '#adr'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:5e506bcf4587be3bc02227667aea0378dd5b9f4f904d97e5683c5358cd1c54b2'
related:
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-06-13-first-filer-attestation-adr]]"
  - '[[2026-11-08-prior-carry-attestation-reference]]'
---

# `prior-carry-attestation` adr: `operator-attested zero for an absent prior-year carry` | (**status:** `accepted`)

## Problem Statement

A Modelo 100 carries pending negative general bases from earlier ejercicios
(boxes 1380, 1382, 1385 and 1388, fed by the bindings declared in
`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:47`
and `:1084` onward). Those carries exist only when a negative general base
liquidable arose in one of the four previous ejercicios (Ley 35/2006 art. 50.3),
so when no earlier return is held they are unknown, never zero. APP-QA D33 found
a filer with no earlier Modelo 100 in the app left with four required boxes and
no way to state that nothing is pending: typing 0 over each box was the only
path, and it reads as a figure the filer entered, not as the statement it is.

## Considerations

- Pending carries are a fact of one declaration's ejercicio. A profile fact would
  carry an absence into later years, where a later negative base can make it false.
- Absent, unknown and proven-zero stay distinct (rule 07): a typed 0 and "nothing
  is pending" must remain distinguishable by verification.
- A later captured earlier return that shows an amount must reach the filer as a
  structured finding. The existing `precedence_tier_divergence` disagreement
  already does this for a caller value against a filed figure
  (`src/cadrumo/domain/modelos/calculation_revision_sources.py:265`).
- The backend serves every word; the window renders.
- The activity-start scoping of `2026-06-13-first-filer-attestation-adr` covers a
  first filer. This record covers a filer whose earlier returns exist outside the app.

## Considered options

- Profile fact ("no pending negative bases"): rejected by the coordinator's ruling;
  it is per-ejercicio, and it would also need a `schema.toml` change.
- Typed 0 on each box: kept as a plain operator value, but it cannot be told apart
  from an attestation and offers no door.
- Served per-declaration form action that records an operator-attested zero on each
  carry: chosen.

## Constraints

- Coordinator ruling of 2026-11-08 (the authorization for this record): use the
  served form action, not a profile fact; record each of the four carries as an
  operator-attested zero on that work unit, with operator-entry provenance and
  revision-bound; keep it distinct from absent and unknown; a contradicting captured
  prior-year amount reaches the user as a structured finding; the words come from
  the backend; no `schema.toml` change.
- Amends `2026-08-24-modelo-edit-contract-adr` D4 by one binding intent kind.
- Revisions stored before this record keep their identity and mean "no attestation".

## Implementation

We will add a binding edit intent, `attest_no_amount`, that the form serves as one
action per declaration over its unresolved earlier-ejercicio carries, and record
its effect on the revision's operator layer as an attested zero.

- Scope: the registry declares which carries take the statement. A binding names
  its family in `absence_attestation`, a closed set whose one member is
  `renta_negative_general_bases_pending`
  (`src/cadrumo/domain/calculations/registry/binding_absence_attestation.py`). The
  schema refuses it on any binding that is not a decimal read from an earlier filing
  (`src/cadrumo/domain/calculations/registry/schema.py:292`). The four Modelo 100
  carries declare it in the 2022 bindings file, and later editions inherit it. No
  other modelo declares a family, so a Modelo 130 or 303 earlier-filing binding is
  never offered the statement.
- Intent: `ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT` carries no value. It is
  admitted only on a writable binding override whose binding declares a family.
  It sets the operator override to zero and marks the binding attested.
  `SET_OVERRIDE_VALUE` and `REMOVE_OVERRIDE` on that binding withdraw the attestation.
- Persistence: `CalculationOperatorLayer` gains `attested_binding_ids`, which must be
  a subset of its binding overrides holding zero. Its identity payload names the set
  only when it is non-empty, so stored revisions keep their identity.
- Resolution and verification: an attested binding resolves to zero at the caller
  tier with attested provenance. The earlier-filing resolver states it as attested
  by the filer, never as unrecorded. A typed value stays an operator entry.
- Contradiction: when an earlier return is later stored with a different amount,
  the existing `precedence_tier_divergence` disagreement is raised against the
  attested zero, with its served accept or revise actions.
- Form: the work form serves one action per declared family, with its action,
  statement and per-carry effect words and the binding addresses it attests. It
  serves the action while a carry of that family is neither resolved, entered nor
  attested. The window stages one `attest_no_amount` intent per address and applies
  them through the ordinary review. The field of an attested carry carries the
  family as `stated_absent` and served origin words, so it never reads as a zero
  that was typed.
- Evidence: real resolvers and real stores, for every Modelo 100 year the registry
  envelope admits.

## Rationale

The statement belongs to the declaration and its revision, where the edit contract
already binds operator values to a baseline and records them in the operator layer.
One intent with a recorded attested set keeps "nothing pending" distinct from a
typed zero, and reusing the disagreement finding makes a later contradiction visible
without a second mechanism.

## Consequences

- The edit contract, the operator layer and the work form change shape. The
  operation contract manifest and the window's wire types are regenerated.
- A filer can complete a first Modelo 100 in the app without an earlier return,
  and a later capture of that return is checked against the statement.
- Another earlier-filing carry takes the action only through a new registry family
  and its served words. This record scopes it to the Modelo 100 carries that D33 found.
- Amended 2026-11-08 on the coordinator's approval of the registry declaration,
  after the plan-close review found the scope inferred from the source kind.

## Amendment 2026-11-11: absence of pending rental expenses

Accepted 2026-11-11 by CADRUMO-PRIME under the operator's delegation, with the decision `2026-11-11-renta-rental-income-source-adr`. One more absence-attestation family is admitted: `renta_capital_inmobiliario_gastos_pendientes`, at row grain keyed by the property row identity, for absence and for stated amounts (amended 2026-11-11 23:25 on the rental decisions ruling, because situaciones 4 and 5 hold no referencia catastral and it is an editable fact). A first year in the app can then state that a property carries no pending expenses from earlier years into 0103, instead of leaving the box unresolved for want of a return the app does not hold.
