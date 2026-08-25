---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3be40d5c0038c4a89baab9a12a8032b6cfd46d3024f90e657f2f36023824ef72'
step_id: 'S01'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Amend the shipped-search-licence-clean rule source to the licence-and-provenance-scoped form ruled in R5 and propagate it with vaultspec-core sync in a coordinated quiet window

## Scope

- `.vaultspec/rules/shipped-search-licence-clean.md`

## Description

- Run live semantic discovery over the decision corpus and documentation-search code through the resident RAG service.
- Read the accepted UserDocs R5 ruling, the current licence rule, the companion plan context, and the execution-record template.
- Amend the rule source to allow only the bounded, provenance-stamped R5 term-embedding plain-data exception while retaining every NC/ND/gated-source, raw-oracle, and heavy-index bar.
- Scaffold this step record with `vaultspec-core vault add exec` and prepare the provider propagation through `vaultspec-core sync`.
- Propagate the amended source through the coordinated quiet window with non-force `vaultspec-core sync --json` and inspect the resulting provider changes.

## Outcome

The shipped-search licence boundary now permits one reviewable term-embedding matrix only in built documentation, never in the wheel, when a pinned named MIT or Apache-2.0 model operates over project-authored or project-bundled vocabulary. The matrix must carry model, exact revision, licence, vocabulary fingerprint, and serialized-size provenance and remain at or below 3 MB. NC/ND/gated-source data, raw retrieval scores, snippets, sparse maps or weights, raw or unbounded vectors, and the generated Pagefind index remain barred.

The source propagated successfully to five deterministic generated provider outputs; the sync reported those five as updated and all other sync items as unchanged.

## Notes

- The live vault RAG result selected the accepted UserDocs ADR at score 0.9685321450; the code probe selected the Pagefind post-build pass and committed relevance-data gate. Both searches completed through the resident service with no fallback.
- The quiet-window collision check found all generated destinations clean before sync. Non-force `vaultspec-core sync --json` updated only the five matching provider outputs; no unrelated generated file was overwritten.
- The checkout had 36 unrelated dirty paths; the exclusive write set was clean before work and peer WIP was preserved. No product-source tree or later plan was touched. P01.S02 and every later step remain unexecuted.
