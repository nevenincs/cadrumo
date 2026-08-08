---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:a9814400911c9620f5424f79853684be04a868a268e5027382b17cb85f33118c'
step_id: 'S175'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Correct the consumes docstring which tells a reader that every row consuming territorial establishment is by design, since it describes the pre-split decision table accurately while the sibling party-fact docstring describes the intent and the law, and both cannot be true. Every later reader currently sees the split as in force while the table carries the pre-split design, and the four declarations of the identification fact read as evidence the migration happened. Lands with the migration rather than before it

## Scope

- `src/cadrumo/domain/iva`

## Description

- Rewrite the decision-table row's consumption docstring so it states that the
  declaration is a claim about the predicate and that the predicate is what must
  honour it, records that the two disagreed on all four intra-community rows,
  and names for each pair the legal reason the identifying State is read.
- Correct the sibling party-fact docstring, whose "the intra-community families
  need the identification and not the place" was a statement about the law
  rather than about the migrated table: those rows do read a residency, and the
  docstring now says what for — placing the supply and excluding the Spanish
  territories — and that reading a residency is not reading it as a
  registration.

## Outcome

The two docstrings no longer contradict each other, and neither now describes a
state the table does not carry. The correction lands in the same commit as the
predicate migration, so no interval exists in which a reader is told the split is
in force while the table keeps the pre-split design.

## Verification

Docstrings carry no gate of their own; what they must not do is break the build
or the docstring cross-link gate. Both were exercised through the Step this rode
with:

    uv run --no-sync pytest src/cadrumo/domain/iva/tests src/cadrumo/application/ledger/tests/test_party_fact_demand.py src/cadrumo/application/invoices/tests/test_m349_clave_follows_the_classifier.py src/cadrumo/domain/calculations/registry/tests/test_ledger_iva_aggregation_binding_reverse_charge.py -n0 -q -m "unit or integration"
    615 passed in 20.07s

    uv run --no-sync ruff format --check <the two changed files>
    2 files already formatted

    uv run --no-sync basedpyright <the two changed files>
    0 errors, 0 warnings, 0 notes

## Notes

The docstring correction is not independently verifiable, which is why it lands
in the same commit as the behaviour rather than as its own change. Landed alone
it would have described a table that did not yet match it, and landed afterwards
it would have left the same contradiction standing for the length of the gap.
