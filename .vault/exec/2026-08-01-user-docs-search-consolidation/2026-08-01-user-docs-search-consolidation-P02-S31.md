---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:3d1b09f99fb4b93a382ff7a2b70be203c5102a28cc85534c2a3d0fd8510becba'
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

### 2026-08-06 LUNA MAX continuation

The existing real Pagefind capture and corrected ephemeral-id/data-url join were rechecked against the temporary provider run. The four-locale/record-kind acceptance boundary remains unproven for a shippable Rung-2 artifact, and the rejected 15/32 composed ladder is preserved as evidence. No source change or plan closure is claimed.

### 2026-08-06 independent browser lexical capture and composed-ladder replay

A real Playwright browser session captured the Pagefind observations for all 32 held-out queries against the local full-injection build at `C:\\Users\\hello\\AppData\\Local\\Temp\\aeat-p02-ladder-311c7392176449ff924a75d44def8817`. The capture followed the source controller contract: sequential Pagefind weight-sorted card search (first 12) followed by normal relevance search (first 6), retaining only records with an opaque `record_id`, the shipped page-band ranks, title-match strength, pass origin, and relevance rank. The run was local and was not a deployment or live-root probe.

The captured observations were bound to `Rung2LadderObservation` and replayed with the current pinned-provider temporary bundle `953ec0851fbbcd43afb460c23a33bf584e6c171a2afee32adb9f966bc3dd7fa2`. The composed ladder produced 32 cases, 16 hits, and 16 misses: held-out miss-rate `0.5000`. The same run measured aggregate token coverage of `92/123 = 0.7479674796747967`, with 20 fully covered cases, 10 below the `0.8` minimum, and 0 zero-covered cases. This is worse than the current bundle's semantic-only diagnostic (`22/32`, `0.3125`) and remains materially above the ratified `0.10` miss-rate bar.

This is reproducible browser measurement evidence, not an acceptance result: the Pagefind build is a local diagnostic build and is not a hash-linked promoted bundle; quantization/top-five loss, licence provenance/size, and per-locale/per-kind gates remain open. No artifact was promoted, enabled, committed, or deployed. P02.S31 remains open pending an accepted hash-linked full-ladder report.

### 2026-08-07 current-checkout build timeout

A fresh diagnostic build was attempted against the then-current shared checkout using `CADRUMO_DOCS_PAGEFIND_MODE=full`, `CADRUMO_DOCS_SKIP_SEQUENCE_CHECK=1`, `CADRUMO_DOCS_JOBS=1`, and `uv run --no-sync python -m dev.docs.build --scope user`. The build populated a partial temporary tree but did not produce `pagefind/pagefind-entry.json` within the ten-minute execution budget. The exact build processes were then stopped after command-line verification; no repository files, generated artefacts, browser configuration, or deployment targets were changed. The partial tree is not treated as evidence, and P02.S31 remains open.

### 2026-08-07 current pushed-head browser capture

Fresh vaultspec-rag grounding and an exact current Pagefind capture were followed by replay through the production Rung-2 ladder comparator. The temporary full-injection tree contained 302 HTML pages and 8,516 unified records; the diagnostic bundle artifact hash was `7907fd6ad903dcb1189286b181639c5e816b061adc4e697497e489f32c6f254d`. The real browser capture covered all 32 held-out queries. Composed results were 16/32 hits and 16/32 misses (miss rate `0.5000`); the same bundle's semantic-only replay was 22/32 hits (miss rate `0.3125`) with 93/123 covered query tokens.

For `modelo 303`, the weighted Pagefind pass does contain `concept:modelo-303`, but legal `DOC` records carry the declared 1.0 weight while the modelo concept carries the declared 0.9 weight. The RAG-grounded D8/R9 contract therefore retains the observed band ordering; no ranking, legal weight, or coverage-threshold change is justified. The evidence remains diagnostic: no bundle promotion, browser enablement, standing-baseline replacement, or plan closure is claimed.

### 2026-08-11 close under ADR Update 12

The lexical half of this row is delivered and at HEAD. The browser capture covered all 32 held-out queries through the shipped controller, and the defect it exposed is fixed in the controller: Pagefind's result object carries an ephemeral id and supplies its URL only through the hydrated data payload, so the earlier join on the result URL assigned the fallback relevance rank to every row. The controller now carries that ephemeral id through card materialisation and joins the relevance pass by it, using the hydrated URL solely as the destination and deduplication authority.

The remaining half of the row, reconciling the composed-ladder drop against the semantic evaluator, is retired with the tier: ADR Update 12 (D12) rules the Rung-2 removal intended, so there is no semantic evaluator to reconcile against and no composed ladder beyond the lexical one. The measured drop that reconciliation would have explained is itself part of the retirement evidence.

The captured observations and the failed acceptance gates are preserved as vault audits rather than promoted, which is what this row asked for.
