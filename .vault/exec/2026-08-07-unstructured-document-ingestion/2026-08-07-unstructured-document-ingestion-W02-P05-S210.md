---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b7eae77dcf06f824d487b91966516c26228714a750857eb44db03e08dc9b442e'
step_id: 'S210'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Replace the stored `counterparty_eu_member_state` field on `Transaction` with `counterparty_country`, an ISO 3166-1 alpha-2 string.
- Derive `counterparty_eu_member_state` as a read-only property, matching the shape `Invoice` already uses.
- Validate the country for SHAPE only, through the same `core.parsing` normaliser that owns `source_jurisdiction`, so one model accepts one spelling.
- Sweep every writer: the two ledger command models, the manual and common action payload builders, the export row and its column header, the filing-evidence projection and its persisted row, and three CLI payload models.
- Rename the CLI option to `--counterparty-country` and the read-view label, with real strings in all four locale catalogues.
- Retire the two superseded catalogue keys the rename orphaned.

## Outcome

A ledger row can represent a counterparty established outside the Union. Before, the establishment field was an enum closed over the Member States: it could say "established in Germany" and could not say "established in the United States", so the only representation a third country had was the ABSENCE of a member state. Absence was also what an unrecorded establishment and a typo looked like.

That collapse is what let the export gate read "not recorded" as "outside the Union". On the issued side outside the Union is export treatment, zero-rated, so a supply could be exempted from a fact nobody had stated.

Four situations that previously all resolved to one blank are now distinct, measured at HEAD:

    US   scope=third_country  status=catalogued
    DE   scope=eu_member      status=catalogued
    XX   scope=None           status=unassigned
    TH   scope=None           status=uncatalogued
    None scope=None           status=None

Validation is deliberately shape-only rather than membership. Membership at the boundary would convert a gap in the bundled vocabulary into an input refusal: `TH` names a real third country the vocabulary does not carry, and refusing it at construction would make a genuine establishment unrecordable while the operator has no way to route around it. Membership stays with the territory resolver and the reason-nothing-resolved with the status reader, so each question is asked where it can be answered.

Read sites needed no change, because the derived property keeps the name and type the field had.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/transactions/tests/test_counterparty_establishment_country.py -n0 -q -m unit
    13 passed in 4.79s

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests src/cadrumo/application/ledger/tests src/cadrumo/domain/transactions/tests -n0 -q -m unit
    2272 tests ran; 37 were DESELECTED by -m 'unit' and never executed.
    2272 passed, 37 deselected, 16 warnings in 210.48s (0:03:30)

    uv run --no-sync python -m dev.locales scaffold --check
    ca.yml: ok
    en.yml: ok
    es.yml: ok
    hu.yml: ok

Both mutations were applied from outside the repository, through a pytest plugin on `PYTHONPATH`, so no tracked file was edited to run them.

Restoring the pre-hardening shape-only country rung: banner printed, 3 holders rebound, 7 invocations, and exactly the `XX` and `TH` cases red while `US` and `DE` stayed green. A mutation that reds everything proves damage; one that reds precisely the cases the hardening added proves the hardening.

Breaking the derived projection to always return nothing: 1 holder rebound, 1 invocation, red on the derivation test alone.

## Notes

A wide sweep reported four failures. All four were proven pre-existing rather than argued: session-start HEAD was extracted with `git archive` into a temporary tree and the same tests were run there with none of this work present, where they failed identically. Three are an end-to-end IVA chain whose intra-community row carries no VAT identification, and one is a CLI module-size gate.

A fifth failure appeared later in the identity-role resolution and was confirmed to pass in that same extracted tree; it belongs to the concurrent document-direction lane.

One earlier wide run reported fourteen failures, including one of this Step's own cases. Re-running the identical selection sequentially returned 2272 passed. The failures were a transient mid-write state in a concurrent lane's files rather than a defect, which is why the reading was repeated before it was reported.

A sweeper committed the source and test changes before they could be committed here, so this Step is split across that sweep and the locale commits made from this lane. The landed content was verified against HEAD rather than assumed from a clean working copy.

The generated CLI sequence recordings under the docs tree still name the old field. They are generated artefacts owned by their own tool and regenerating is tree-wide, so they were left and rowed separately.
