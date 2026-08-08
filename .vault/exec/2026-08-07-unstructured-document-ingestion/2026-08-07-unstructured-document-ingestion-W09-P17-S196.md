---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f0fcbc2d65f21437cba842a4da4b6effed873cd2c6fdeaa93f681ccb4422c6d2'
step_id: 'S196'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Widen the bundled country vocabulary, bounded by an argued principle

## Scope

- `src/cadrumo/_data/registry`

## Description

- Complete the two third-country blocs the vocabulary already declared as criteria and did not meet: Latin America, carried at 8 of 19, and the European non-EU sovereign states, carried at 9 of 20.
- Complete the Maghreb, where Morocco was carried on a proximity argument that says nothing about Morocco in particular.
- Ground every added alpha-2 code and Spanish name against AEAT's own country register, which ships bundled inside the Manual práctico de Sociedades.
- Record the boundary argument in the table header, including why the complete ISO register was refused and which jurisdictions are excluded by decision rather than backlog.
- Record what the alpha-3 column is and is not grounded in, since nothing in this tree ships an alpha-2-to-alpha-3 correspondence.
- Extend the widening tripwire to the two newly named exclusions.
- Repoint an alpha-3 fixture anchor whose chosen code this widening admitted.

## Outcome

Twenty records added, taking the table from 58 to 78. Every one resolves to the third-country scope from both legs, no code is ambiguous across the two catalogues the resolver unions, and the only code where those catalogues still differ is the pre-existing Northern Ireland case.

The boundary is argued rather than drawn at a convenient size. Completing the two declared blocs is an incompleteness argument, not a widening one: the criteria were written down and the data never met them. The complete ISO register was refused, and the reason is that the per-entry cost of the code axis being lower is a property of a code-only register that does not exist yet. This is one table, so every record admitted for its code also carries names and pays the full name-axis cost in reviewer attention and in the two collision modes the loader refuses the whole table over.

The load-bearing exclusion is the one the widening could most easily have got wrong. Membership of this table is what makes the country rung fire, and the rung has exactly three outcomes with no fourth, so listing a jurisdiction asserts that ordinary third-country treatment is right for it. Monaco fails that test: it is treated as France for VAT under the Directive, so listing it would resolve a Monegasque counterparty to a third country and, on the issued side, exempt a supply that is not exempt. That is the same silent under-declaration the country rung was narrowed to close, re-entered through the data instead of the code. Gibraltar is excluded as a territory rather than a state, and Kosovo because its code sits in the user-assigned range the resolver reads as denoting nothing, so admitting it would make one code both catalogued and reserved.

What is still excluded is stated by name rather than left as an implicit backlog: the second tier of Asian manufacturing counterparties, the Gulf states beyond the Emirates, Egypt, Nigeria, and the Vatican. Each is a defensible addition the day somebody measures the traffic rather than the plausibility, which is the standard the added entries were held to and the one that list fails.

## Verification

Every added code and Spanish name checked against the bundled AEAT register before authoring:

    BO Bolivia / CR Costa Rica / CU Cuba / DO Dominicana, República / EC Ecuador
    GT Guatemala / HN Honduras / NI Nicaragua / PA Panamá / PY Paraguay
    SV Salvador, El / AL Albania / BA Bosnia-Herzegovina / LI Liechtenstein
    MD Moldavia / ME Montenegro / MK Macedonia / SM San Marino / DZ Argelia / TN Túnez

All three loader invariants checked against the real normaliser BEFORE landing, rather than from a red gate, because the loader refuses the whole table on any of them:

    COLLISIONS: none
    new codes already present: none

The union invariant, after landing:

    records 78 codes 78
    EU not in table (expected XI only): ['XI']
    ambiguity: table codes classed non-catalogued: []
    all new resolve third_country: True

Owner-surface lanes:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m "unit"
    646 passed in 16.30s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests -n0 -q -m "integration"
    22 passed, 1731 deselected in 80.39s (0:01:20)

The tripwire against a bulk widening, proven to bite by installing the CLDR territory register from outside the repository:

    [widening] CLDR territory vocabulary installed (264 codes)
    [widening] widened vocabulary consulted 14 times
    6 failed, 7 passed

Monaco, the two Spanish territory codes and the three non-country codes all reddened. The invocation counter is the control: a widening whose codes never reached the resolver would leave the guard green for a reason unrelated to the guard being sound.

## Notes

The alpha-3 column has no bundled authority and the header now says so rather than implying one. Nothing in this tree ships an alpha-2-to-alpha-3 correspondence: not the corpus, and no installed package. What defends the column is mechanical rather than documentary, and the loader's three refusals catch a contradiction but cannot catch a value that is wrong and consistent. It is the weakest column in the file and is recorded as such.

The bundled AEAT register is authoritative and not infallible. It still spells North Macedonia under its pre-2019 name. The current name is carried first and the historical one kept beside it, because documents print both; the corpus was read and then judged rather than copied.

One fixture anchor reddened and was repointed rather than deleted. A case proving the vocabulary is bounded had chosen Bolivia's alpha-3 as its outside-the-table example, and adding Bolivia falsified it. That is the anchor performing exactly the service it exists for, so it was moved to Thailand, which is a NAMED exclusion in the header rather than a country nobody had reached — if that one is ever admitted, the case is right to red again.

Six tests in the ledger preflight surface are red at HEAD and are not this change: a peer lane added an `UNSUPPORTED_IVA_RATE` member to the aggregation issue reason enum without extending the preflight's total mapping over it, so the mapping raises. Confirmed against HEAD directly — the enum carries the member and the mapping does not. Untouched, and reported to the coordinator.
