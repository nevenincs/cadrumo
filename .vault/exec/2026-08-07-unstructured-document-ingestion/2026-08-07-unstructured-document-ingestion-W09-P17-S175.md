---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:34c6db92bdd8ed79d560e541d5e998f97060daf8e926ecd48e97b33afdd6b6da'
step_id: 'S175'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S175 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Correct the consumes docstring which tells a reader that every row consuming territorial establishment is by design, since it describes the pre-split decision table accurately while the sibling party-fact docstring describes the intent and the law, and both cannot be true. Every later reader currently sees the split as in force while the table carries the pre-split design, and the four declarations of the identification fact read as evidence the migration happened. Lands with the migration rather than before it and ## Scope

- `src/cadrumo/domain/iva` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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

<!-- Where the evidence is that something RAN, quote the instrument rather than
     summarising it: the invocation, then the runner's verbatim summary line.

         uv run --no-sync pytest <paths> -m integration -n 0
         15 passed in 10.35s

     The invocation shows the selection (marker expression and path scope); the
     summary line shows what that selection produced. A run that selected nothing
     exits zero and reads as green, so a paraphrase such as "the tests pass"
     discards exactly the part a reader needs. Quote, do not summarise. -->

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
