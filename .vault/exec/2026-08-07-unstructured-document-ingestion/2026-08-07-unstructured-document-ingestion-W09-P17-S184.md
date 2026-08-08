---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1ab442c4a4fdc41c3631c2a29e031c180cec18343f391985649fbf766247705c'
step_id: 'S184'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Gate the unassigned-country ruling with the three fixtures the amendment names

## Scope

- `src/cadrumo/domain/iva`
- `src/cadrumo/application/ledger`

## Description

- Add the domain boundary gate covering the three named user-assigned codes against both legs, the catalogue-gap case, the status axis, and the never-degrades-to-Spain property.
- Add the application gate proving an unassigned code cannot reach a zero-rated category, that a genuine catalogued third country still classifies as the export, and that the two finding kinds are distinguishable.
- Rewrite the resolver test whose discriminating control used reserved codes as stand-ins for third countries, so the control no longer shares the defect's premise.
- Extend the deterministic check-name stamp to the newly enrolled check.

## Outcome

All three fixtures the amendment names by hand are carried, plus the opposite-direction controls the ruling's failure mode demands. The reserved codes yield no scope from the resolver, the structured leg and the assembly; an issued-side invoice stating one never assembles, so the classifier is unreachable rather than merely answering differently; and a real ISO jurisdiction the bundled vocabulary omits raises the catalogue-gap kind rather than the typo kind.

The negative controls are the part most likely to rot, so they are keyed on the set of both country kinds derived from the members rather than on one kind: a control naming only the typo kind would pass while the catalogue-gap kind false-fired on every catalogued country.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests -n0 -q -m "unit"
    1699 passed, 22 deselected, 15 warnings in 215.67s (0:03:35)

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests src/cadrumo/core/tests -n0 -q -m "integration"
    22 passed, 2598 deselected in 87.86s (0:01:27)

Mutation proof of the resolver gate, from a plugin outside the repository:

    19 failed, 39 passed in 1.46s
    [mutation] patched callable invoked 34 times: ['AA', 'BR', 'DE', 'ES', 'JP', 'QM', 'QQ', 'TH', 'US', 'XA', 'XI', 'XX', 'ZZ']

Mutation proof of the structured leg, which the first mutation does not reach:

    3 failed, 33 passed in 1.38s
    [mutation] patched callable invoked 13 times: ['AA', 'BR', 'JP', 'QM', 'QQ', 'TH', 'US', 'XA', 'XX', 'ZZ']

## Notes

Each mutation carries its own invoked-callable control rather than relying on the load banner. A single-target mutation has no sibling to expose a probe that never reached the patched callable, and passing tests under a mutation that missed its target is indistinguishable from a gate that does not bite. The structured leg was mutated separately for exactly that reason: it passed under the first mutation because it holds its own membership check, which is a pass the first control could not have distinguished from a missing gate.
