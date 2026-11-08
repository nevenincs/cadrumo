---
tags:
  - '#adr'
  - '#prior-carry-attestation'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:fff990f4653da5f692ca32167749013f751ea52ff287872b10b57e957974f3d7'
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

- Intent: `ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT` carries no value. It is
  admitted only on a writable binding override whose source is an earlier filing.
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
- Form: the work form serves the action, with its words and the binding addresses
  it attests, while earlier-ejercicio carries are required and neither resolved nor
  attested. The window stages one `attest_no_amount` intent per address and applies
  them through the ordinary review.
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
- Other earlier-filing carries can be served the same action later; this record
  scopes it to the Modelo 100 carries that D33 found.
