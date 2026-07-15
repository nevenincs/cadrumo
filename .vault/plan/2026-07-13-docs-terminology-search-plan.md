---
tags:
  - '#plan'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-15'
tier: L3
related:
  - '[[2026-07-13-docs-terminology-search-adr]]'
  - '[[2026-07-15-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `docs-terminology-search` plan

## Wave `W01` - Measure

Ground every later decision in committed measurements: corpus coverage of the shipped relevance mapping, the held-out miss-rate baseline, and the synonym ratification queue state.

### Phase `W01.P01` - Coverage, miss-rate, and queue reports

Read-only measurement runs against the resident RAG service producing committed reports.

- [x] `W01.P01.S01` - Generate the coverage report: derive the candidate query surface from calc-grade casilla labels/sections and legal-catalogue provision vocabulary, list every derivable target with no inbound relevance entry, and commit the report; `dev/docs/terminology/, .vault/audit/`.
- [x] `W01.P01.S02` - Run the held-out golden queries through the shipped relevance mapping with the miss-rate machinery and commit the baseline miss-rate report; `dev/docs/terminology/_miss_rate.py, .vault/audit/`.
- [x] `W01.P01.S03` - Inventory the synonym candidate queue (mined, unratified) and commit the inventory with a ratify-or-clear disposition per candidate; `dev/docs/terminology/_synonym_mining.py, .vault/audit/`.

## Wave `W02` - Hook wiring

Wire the repo extractors into the shipped upstream vaultspec-rag preprocess seam, prove per-kind parity against the committed sidecars, then cut over atomically and retire the sidecar tree.

### Phase `W02.P02` - Adapter, rules, parity, cutover

Build the upstream-schema adapter and rule file, gate config validity, prove parity per source kind, then one atomic cutover commit.

- [x] `W02.P02.S04` - Implement the upstream-schema adapter: serialize the repo PreprocessOutput to the upstream PreprocOutput JSON contract behind a python -m entry point, with unit tests against the pinned schema major; `dev/docs/preprocess/`.
- [x] `W02.P02.S05` - Author the preprocess rule file for the four corpus source kinds and add the strict preprocess-check repo gate test; `.vaultragpreprocess.toml, dev/docs/preprocess/tests/`.
- [x] `W02.P02.S06` - Prove per-kind parity: preprocess run-one output text equals the committed sidecar text for a representative source of each kind, asserted by a committed test; `dev/docs/preprocess/tests/`.
- [x] `W02.P02.S07` - Re-scoped cutover (ADR Update 1): exclude the extracted sidecars from the dev index via .vaultragignore, retarget the terminology resolver path rules to source-file paths, correct the stale preprocess docstring to describe the sidecars' product-payload role, keep the hook-vs-sidecar parity gate as a permanent lock, and prove an equal-or-superset sweep target set - one explicit-path commit; `the sidecar tree stays (it is the wheel's corpus payload and the shipped search's index source); `.vaultragignore, dev/docs/terminology/_resolution.py, dev/docs/preprocess/__init__.py, dev/docs/preprocess/tests/test_hook.py`.

## Wave `W03` - Widen

Extend the sweep query vocabulary from the coverage report over the bundled legal corpus and casilla registry, re-run the sweep, and land the widened relevance mapping as a reviewed diff.

### Phase `W03.P03` - Vocabulary widening and sweep re-run

Author the widened query vocabulary from the coverage report, reindex, sweep, wrangle, and land the reviewed mapping diff.

- [x] `W03.P03.S08` - Author the widened query vocabulary from the coverage report through the Handbook enrolment surfaces, keeping the synonym ratification ratchet; `src/cadrumo/_data/terminology/`.
- [x] `W03.P03.S09` - Run incremental reindex then the widened sweep through the resident service, wrangle through the typed resolution, and land the widened relevance mapping as a reviewed committed diff; `src/cadrumo/_data/terminology/relevance/relevance.json`.

## Wave `W04` - Rung-2 gate

Take the deferred rung-2 decision on the post-widening miss-rate number per ADR D3 and commit the measurement either way.

### Phase `W04.P04` - Gate decision

Re-measure the held-out miss-rate post-widening and apply the ADR D3 numeric gate.

- [x] `W04.P04.S10` - Re-run the held-out miss-rate over the widened mapping, commit the measurement, and apply the ADR D3 gate: implement rung 2 only above the ten-percent top-five miss line, else record the standing baseline; `dev/docs/terminology/, .vault/audit/`.

## Wave `W05` - Result display classes and user-first ranking

Implement ADR 2026-07-15 D7/D8: a closed display-class taxonomy (casilla box, modelo document, cli terminal, technical code, doc question-mark) derived once at the injection seam and shipped in the Pagefind meta, rendered as licence-clean inline-SVG icons by the shared search controller, and a single declared user-first weight table (facts, modelo, casilla, cli, user docs, technical last) replacing the per-kind base weights.

### Phase `W05.P05` - Display-class derivation and weight table (Python)

Derive the closed display class per unified record at the injection seam, ship it in the Pagefind meta, and move the base-weight authority to one per-class table; unit gates prove total coverage and the declared ordering.

- [x] `W05.P05.S11` - Declare the closed ResultDisplayClass StrEnum and the single derivation function (record kind + concept domain + page path prefix to class) beside the unified record, with a unit gate proving every projected record maps to exactly one class; `dev/docs/terminology/_unified_record.py, dev/docs/terminology/tests/test_unified_record.py`.
- [x] `W05.P05.S12` - Ship display_class in the injected Pagefind meta and replace the per-kind base-weight table with the one declared per-class user-first table (facts, modelo, casilla, cli, user docs, technical last), updating kind_base_weight consumers and tests; `dev/docs/pagefind_inject.py, dev/docs/terminology/_unified_record.py`.
- [x] `W05.P05.S13` - Gate the weight table: its ordering matches the ADR D8 ladder verbatim and every display class carries exactly one weight, failing on any unmapped class; `dev/docs/terminology/tests/test_unified_record.py`.

### Phase `W05.P06` - Controller iconography and re-ranking (JS + gates)

Render the per-class inline-SVG icons and class-scoped styling in the shared search controller, consume the shipped per-class weights in the compose ladder unchanged, and extend the Playwright palette-ranking gate with the two new ordering assertions.

- [x] `W05.P06.S14` - Render one hand-authored inline-SVG icon and class-scoped styling per display class in the shared search controller card row (box, document, terminal, code, question mark), reading the shipped display_class meta only, never re-deriving it in JS; `docs/_static/cadrumo-docs.js, docs/_static/cadrumo-docs.css`.
- [ ] `W05.P06.S15` - PARTIAL (ADR D8 residual). Consume the shipped per-class weights in the compose ladder unchanged and extend the Playwright palette-ranking gate. Casilla-above-cli ordering on a mixed query delivered and gated (test_palette_ranking casilla-above-cli). The how-to-page-above-api-stub full-text ordering is deferred to W05.P06.S17, structurally blocked because directory-indexed full-text pages carry no display_class or weight, and this step stays unchecked until S17 lands its gate; `docs/_static/cadrumo-docs.js, dev/docs/tests/test_palette_ranking.py`.
- [x] `W05.P06.S16` - Coordinate the controller edits with the in-flight palette-host extraction owner: diff cadrumo-docs.js before editing, land via explicit-pathspec commits, and verify icons render on both hosts (Ctrl-K dialog and search page) once the extraction lands; `docs/_static/cadrumo-docs.js, docs/_templates/search.html`.
- [ ] `W05.P06.S17` - Emit display_class as data-pagefind-meta on the generated and built pages so directory-indexed full-text page hits carry a ranking weight, completing the D8 user-documentation-above-technical ordering for full-text results, gated by a browser assertion that a how-to page outranks an api stub on a mixed query; `docs/conf.py, dev/docs/pagefind_index.py, dev/docs/tests/test_palette_ranking.py`.

## Description

## Steps

## Parallelization

## Verification
