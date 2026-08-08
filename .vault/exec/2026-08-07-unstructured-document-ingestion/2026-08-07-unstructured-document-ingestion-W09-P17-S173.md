---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8e2687555f0bdc2d965e83819f2c4e00ab0be9fb95565aebfde34c1c30e3d00f'
step_id: 'S173'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Migrate the intra-community predicates onto the identification axis, since the fact split landed at the model and producer layers and NOT in the decision table: the criteria carry both identification fields, the producer populates them at all three construction sites, four rows declare consuming the identification fact, and no predicate reads either field even once. Those rows key on a customer tax status that says the customer is registered somewhere and never where, substituting an establishment test for the identification the law requires, so a customer identified in another Member State whose establishment the reader could not settle fails to classify and a legitimate exempt intra-community supply is refused as missing data rather than reported as a defect. Ground the change against LIVA art. 25, which exempts on the acquirer being identified in another Member State, with a worked oracle, since this changes which operations classify and is legal behaviour rather than a refactor

## Scope

- `src/cadrumo/domain/iva`

## Description

- Confirm the measurement independently: no predicate in the closed IVA
  classification table read either identification field, while four rows
  declared the fact consumed.
- Verify LIVA art. 25.Uno against the bundled consolidated corpus and take its
  operative clause verbatim as the grounding for the change.
- Land the gate first and observe it red against the pre-change table.
- Add a module-private helper expressing the statutory condition — a VAT
  identification assigned by a Member State other than Spain — refusing both an
  absent State and Spain itself.
- Migrate the goods pair, supply and acquisition, to read the counterparty's
  identifying State as the operative condition, retaining a narrow establishment
  read that excludes the Spanish territories, which are not otro Estado miembro.
- Migrate the services pair to read the identification beside the establishment
  the place-of-supply articles require, since their categories select a Modelo
  349 clave against a counterparty NIF-IVA.
- Correct the two docstrings that contradicted each other and described a
  migration that had not happened.

## Outcome

The four intra-community rows now read the fact they declare. A supply to an
acquirer identified in another Member State classifies as exempt whatever the
acquirer's establishment resolves to, and an operation carrying no identifying
State, or a Spanish one, reaches the fallthrough sentinel for operator review
instead of being exempted silently.

The change is behavioural in both directions, and the tightening direction is
deliberate: operations previously exempted on establishment alone now refuse.
Refusing is the safe direction against the standing prohibition on silent
under-declaration; being exempted without the statutory condition was not.

Two limits are recorded rather than smoothed. The criteria model carries no
UNKNOWN territorial scope, so an identified counterparty whose establishment is
entirely unsettled cannot be expressed at the table; the closest expressible
case, an establishment settled outside the Union, is what the gate exercises.
And the criteria producer still demands both parties' establishment
unconditionally, ahead of any branch, so that population is still stopped one
layer above this one.

## Verification

The gate red before the change and green after, same invocation:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_intra_community_identification_axis.py -n0 -q -m unit
    11 failed, 2 passed in 0.96s

The classification surface and its consumers, after:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests/test_party_fact_demand.py src/cadrumo/application/invoices/tests/test_m349_clave_follows_the_classifier.py src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding_reverse_charge.py -n0 -q -m "unit or integration"
    615 passed in 20.07s

Unit lane over the dependent trees:

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/domain/invoices src/cadrumo/domain/transactions src/cadrumo/domain/calculations/registry src/cadrumo/application/aggregation src/cadrumo/application/invoices -n0 -q -m unit
    8 failed, 5755 passed, 97 deselected, 2 warnings in 1074.09s (0:17:54)

Integration lane over the same trees less the registry:

    uv run --no-sync pytest src/cadrumo/domain/iva src/cadrumo/domain/invoices src/cadrumo/domain/transactions src/cadrumo/application/invoices src/cadrumo/application/aggregation -n0 -q -m integration
    74 passed, 1982 deselected in 300.77s (0:05:00)

Mutation, driven from a pytest plugin outside the repository so nothing under
the source tree changed, with the invocation count of the patched callable as
the positive control that the patch reached what the tests invoke:

    MUTATION=permissive  exit=1  invocations=25  9 failed, 4 passed in 1.50s
    MUTATION=never       exit=1  invocations=24  8 failed, 5 passed in 1.35s

Format, lint and type check over the two changed files reported two files
already formatted, all checks passed, and zero errors.

## Notes

The eight unit-lane failures are outside this surface and are not triaged to
this Step. All eight sit in the registry tree — export decimal parsing, the
loader disk cache, formula-construct parity, an M100 worked example, the two
M390 routing mutation gates and the revision-span design re-layout gate — and
none of the seven modules carries a single reference to the classifier, its
criteria record or the party-fact enum. The working tree also holds substantial
concurrent peer edits in the registry and IVA establishment surfaces.

One collection error is present at HEAD and is likewise not this Step's: the
ledger classification-assembly test module cannot import, because the einvoice
adapter facade re-exports a parsed-invoice symbol its private parser module no
longer defines. The adapter carries no working-tree diff, so the break is in the
committed state rather than in anyone's uncommitted work.

No external numeric oracle was authored for this change and none is claimed. The
positive intra-community supply case already has one — an AEAT Manual práctico
IVA 2025 worked example replayed against the classifier, whose recorded operation
carries an identifying Member State and which stays green. What this Step adds is
the discrimination between the two party facts, for which no numeric authority
exists, so its expectations rest on the bundled consolidated statutory text and
on gate wiring and refusal behaviour instead.
