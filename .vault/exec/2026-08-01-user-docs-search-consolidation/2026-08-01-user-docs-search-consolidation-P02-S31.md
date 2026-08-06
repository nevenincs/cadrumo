---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:8b40c1b959227f34337dae94648e4e66dea1f97be2b6440f0791d48a0f7b6b40'
step_id: 'S31'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Capture the real Pagefind lexical observations for the held-out corpus through the browser controller, reconcile the composed-ladder drop against the semantic evaluator, and preserve any failed gate as evidence

## Scope

- `dev/docs/terminology/`
- `docs/_static/cadrumo-docs.js`

## Description

- Run fresh `vaultspec-rag` searches over the accepted display-class ladder, the Rung-2 browser contract, Pagefind result handling, and the authoritative record manifest.
- Build the complete local user documentation tree with full Pagefind injection in a temporary directory, retaining the documented sequence-check bypass as an explicit diagnostic boundary.
- Serve that exact tree and capture the two real Pagefind passes through Playwright for all 32 held-out queries.
- Reconcile the observed lexical rows with the accepted D8 band-first ladder and the R9 semantic composition boundary.
- Repair the Pagefind relevance join through an exclusive LUNA MAX worker, preserving the existing ranking and destination contracts.

## Outcome

The real browser capture covered all 32 held-out queries. The weighted Pagefind pass returned authoritative legal, concept, casilla, and CLI records; it did not admit ordinary full-text pages. For `modelo 303`, the exact model concept was present in the weighted pass but below non-direct legal DOC records, so the first five rows remained legal records. Sol medium confirmed this is contract-compliant: D8 is band-first and its exact/prefix/substring/relevance rule is a within-band tie-break; R9 places exact identity ahead of semantic fallback, not ahead of another lexical display band.

The installed Pagefind result object exposes an ephemeral `id` and `data()`; its URL is supplied by the hydrated data payload. The controller's prior `result.url` join therefore assigned the fallback relevance rank to every row. The LUNA MAX worker now carries the ephemeral Pagefind id through card materialisation, joins the relevance pass by id, and continues to use `data.url` for the destination and deduplication authority. No semantic representation, threshold, display-class weight, or legal ranking policy was changed.

The Rung-2 acceptance gate remains rejected. The browser capture is diagnostic evidence and does not enable the bundle, promote a new baseline, close P02.S04-P02.S07, or authorize deployment.

## Verification

`uv run --no-sync vaultspec-rag search "Pagefind weighted card pass legal records display class weight ranking relevance result.url data url" --type code --port 8766 --timeout 120`

The live RAG result selected the Pagefind card-pass tests, the shared controller, the unified-record weight authority, and the injection metadata seam. Companion vault searches selected the D8 audit/ADR and the Rung-2 browser/manifest contract.

`uv run --no-sync python -m dev.docs.build --scope user --out-dir <session-scratch-dir>\aeat-p02-ladder-311c7392176449ff924a75d44def8817`

The local full-injection output contains `pagefind/pagefind-entry.json` and 302 HTML pages. The run used `CADRUMO_DOCS_PAGEFIND_MODE=full`, `CADRUMO_DOCS_SKIP_SEQUENCE_CHECK=1`, and `CADRUMO_DOCS_JOBS=1`; it is not a full-green Sphinx acceptance run.

`npx --yes --package @playwright/cli playwright-cli -s=aeat-ladder open http://127.0.0.1:8877/`

The browser session captured Pagefind card/page counts and composed top-five rows for all 32 held-out queries from the temporary tree.

`uv run --no-sync pytest -q -m integration dev/docs/tests/test_search_page_inline_ladder.py dev/docs/tests/test_palette_ranking.py`

`3 passed in 43.86s`

`uv run --no-sync pytest -q dev/docs/terminology/tests/test_rung2_evaluation.py`

`10 passed in 9.57s`

`node --check docs/_static/cadrumo-docs.js`

Passed with exit code 0.

`git diff --check -- docs/_static/cadrumo-docs.js dev/docs/terminology/_rung2_evaluation.py dev/docs/terminology/tests/test_rung2_evaluation.py`

Passed with exit code 0.

## Notes

The first browser-test invocation without `-m integration` selected zero tests because the project default excludes integration; it was not treated as green. The explicit integration rerun is the valid browser evidence.

The local HTTP server and browser session were used only for a temporary local tree. No live deployment, generated-artifact promotion, commit, push, or Rung-2 browser enablement occurred. The full local build still carries the sequence-check bypass and the standing locale/deployment gates remain open.

The real Pagefind capture does not close the held-out miss-rate gate. P02.S31 remains open pending an accepted, reproducible full-ladder measurement; P02.S32 remains open for an independently versioned RAG-grounded query/alias authority.

### 2026-08-06 formal review synchronization

The formal LUNA MAX code review recorded PASS with only low-severity findings across evaluator invariants, deterministic ordering, the Pagefind id/data-url join, D8 preservation, security/licence boundaries, and shared-worktree scope. The complete browser integration selection was independently rerun as `uv run --no-sync pytest -q -m integration dev/docs/tests/test_palette_ranking.py dev/docs/tests/test_search_page_inline_ladder.py dev/docs/tests/test_search_page_fulltext_class_ranking.py`, returning `4 passed in 38.89s`. This review does not close P02.S31 or the Rung-2 acceptance gate.
