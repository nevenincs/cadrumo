---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:b332890aa57f5d5edc73418401d1907a65ec38a4797cb2ca2410db632836573e'
step_id: 'S72'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-14-cadrumo-product-rename-audit]]"
---

# Update documentation site identity, titles, marks, and generated API configuration

## Scope

- `docs/conf.py`
- `docs/index.md`
- `docs/_static/cadrumo-favicon.svg`
- `docs/_static/cadrumo-mark-dark.svg`
- `docs/_static/cadrumo-mark-light.svg`
- `dev/docs/tests/test_docs_build.py`

## Description

- Classify the work as a documentation identity and static-asset refinement while preserving the existing information architecture.
- Ground every identity use against the binding product-name decision, the central product identity declaration, semantic RAG results, exact search, and repository history.
- Render sentence and read-aloud prose as Cadrumo, visual wordmark lettering and non-read-aloud product identity as CADRUMO, machine identifiers as `cadrumo`, the human CLI as `aeat`, and the Spanish authority as AEAT.
- Replace generic metadata and footer language with reader-facing preparation, export, self-filing, and qualified-professional boundaries.
- Refine the landing-page introduction and search guidance without changing its navigation hierarchy or generated API structure.
- Add a focused real Sphinx build that verifies rendered browser, OpenGraph, heading, footer, copyright, SVG accessibility, and wordmark identity.
- Apply the zero-context editorial review's minor revisions to read-aloud capitalization, sentence length, search wording, and support-boundary terminology.

## Outcome

- The documentation shell now presents Cadrumo consistently in prose while retaining the CADRUMO visual identity and the binding `aeat` CLI name.
- Both shipped wordmarks render CADRUMO, and their accessible labels plus the favicon label read naturally as Cadrumo.
- The API scaffold remains exactly aligned: 1,149 source modules, 1,149 stubs, and zero missing, orphaned, or stale stubs.
- The focused rendered identity test, all eight API scaffold tests, Ruff, formatting, Ty, and the full warning-as-error nitpicky Sphinx build pass.
- Audit `2026-07-14-cadrumo-product-rename-audit` records that the Phase 3 refined-wireframe and Phase 8 final-document approvals are granted by the principal-documentation-writer session, the standing operator-designated approval authority for user documentation, on the basis of its own direct review of `docs/conf.py`'s `PRODUCT_IDENTITY`-derived project identity and the shipped product marks at HEAD. The prior `c3f6e207f6` review's FAIL verdict on this same missing-approval-evidence ground is resolved; its separate low-severity note (state the narrow Ty-passing scope and the pre-existing `docs/conf.py` diagnostics) is a documentation-precision point about this record's own reporting, not a content defect, and is corrected here: Ty passes for the added rendered-identity test; running Ty across both changed Python files also surfaces three pre-existing TOML object-narrowing errors and one pre-existing missing-override-decorator diagnostic in `docs/conf.py`, none introduced by this Step.

## Notes

- No information-architecture change was required, so the current approved hierarchy was preserved rather than re-wireframed.
- No legacy static filenames or generated API drift existed; no generated API file was rewritten.
- OpenGraph derives the rendered page description from page content, so the focused test verifies its rendered site identity while the standalone Sphinx metadata description remains configured separately.
- Concurrent unrelated worktree changes were excluded from this step and its commit.
