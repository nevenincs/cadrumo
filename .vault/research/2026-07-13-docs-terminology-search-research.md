---
tags:
  - '#research'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:7f6ecaf8fcaaa05e0e050887f714dd1fb41aa202937885dd8155db36f97e6a71'
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-15-docs-terminology-search-adr]]'
---

# `docs-terminology-search` research: `corpus-derived precompiled search status and next wave`

Status survey of the precompiled semantic-search feature the operator
proposed — the vaultspec-rag-derived, preprocessor-hook-fed, bundled
legal-and-modelo-corpus-grounded search shipped with the docs — plus the
grounded gap list for the next wave. Prompted by an operator review on
2026-07-13 questioning whether the project regressed to a hand-maintained
glossary instead of the precompiled RAG mapping.

## Findings

### The proposed architecture shipped; it is not a glossary regression

The accepted architecture (decision D6 of the 2026-06-10 ADR) is exactly
the operator's proposal: the resident dev vaultspec-rag service is the
build-time compilation oracle; a query-vocabulary sweep runs semantic
retrieval ahead of time on the GPU dev box; outputs are wrangled through a
typed chunk-to-target resolution layer and land as committed, licence-clean
(SPLADE-laundered: rankings and target ids only, never vectors or sparse
weights) relevance data. The shipped surfaces at HEAD:

- Sweep + wrangling pipeline: `dev/docs/terminology/` (`_sweep`,
  `_resolution`, `_synonym_mining`, `_miss_rate`, unified `SearchRecord`
  projection) with developer CLIs (`sweep.py`, `synonyms.py`).
- Committed relevance data:
  `src/cadrumo/_data/terminology/relevance/relevance.json` — 72 queries,
  29 approved concepts, 0 failed queries, score floor 0.5.
- Shipped search: Pagefind index regenerated per build;
  `dev/docs/pagefind_inject.py` injects unified records — concept cards
  (tier 1), casilla projections from the registry authority plus CLI
  surface records (tier 2), full page text (tier 3) — per language, with
  relevance boosts applied from the committed mapping.
- Reader surface: the Ctrl/Cmd-K palette in `docs/_static/cadrumo-docs.js`
  with within-tier tie-breaking; gated end-to-end in a real browser
  (`dev/docs/tests/test_palette_ranking.py`, prorrata smoke gate).

The glossary the operator saw is decision D7 of the same accepted ADR, not
a parallel hand-maintained document: it is GENERATED at builder-inited from
the Terminology Handbook (single-declaration source, approved-tier-only per
the 2026-06-15 ADR D1/D2 demotions), uncommitted like `docs/cli/`, and
exists to give every concept a stable `:term:` anchor the palette's term
cards and hover tooltips resolve to. Maintenance surface is the Handbook
concept set (29 approved concepts), not free prose.

### The upstream preprocess-hook seam SHIPPED; this repo has not wired it

Corrected by operator review 2026-07-13: upstream vaultspec-rag already
implements the pre-index document preprocessing seam. The live CLI exposes
`vaultspec-rag preprocess list / check / run-one`, driven by a project-side
`.vaultragpreprocess.toml` rule file. This repository carries NO such file
(`preprocess check`: "No preprocess rules configured"), so the hook sits
unused. The repo instead still runs the interim path adjudicated in D6:
`dev/docs/preprocess/` extracts the binary/unsupported grounding corpus
(BOE normatives HTML with article-delimiter-aware splitting, Diseños de
Registro workbooks, corpus PDFs, unsupported-text tail) into committed
`*.extracted.md` + `*.extracted.json` sidecars the walker indexes as
ordinary markdown. The docstring of `dev/docs/preprocess/__init__.py`
still claims "the walker has no preprocess-hook capability yet" — that
claim is STALE and must be corrected when the hook wiring lands.

### Grounded gaps for the next wave

1. **Wire the shipped upstream hook.** Author `.vaultragpreprocess.toml`
   rules that route the repo's existing extractors (`_html`, `_pdf`,
   `_workbook`, `_text` in `dev/docs/preprocess/`) through the upstream
   preprocess seam, validated with `vaultspec-rag preprocess check` and
   `run-one` per source kind. Until then, extraction freshness depends on
   re-running the sidecar preprocessors and an explicit incremental
   reindex before every sweep (the watcher-staleness hole in D6).
2. **Sweep coverage vs corpus breadth.** 72 queries over 29 approved
   concepts is the ratified vocabulary, but the bundled legal corpus
   (`corpus/normatives/html/`) and the full modelo/casilla registry offer a
   far larger derivable query surface. The next sweep wave should measure
   coverage: which legal provisions and casilla families resolve to NO
   shipped search record.
3. **Rung 2 remains gated, unmeasured.** The static term-embedding matrix
   (~1–3 MB int8 over the closed vocabulary, client-side cosine — the true
   offline semantic rung) is deferred behind a miss-rate measurement over a
   held-out real-query set (`_miss_rate`, golden queries). The measurement
   has not been taken; the gate cannot fire either way until it is.
4. **Synonym ratification queue.** Mined paraphrase candidates require the
   human allowlist-with-reason ratchet before they enter the shipped index;
   queue state should be inventoried and either ratified or cleared.
5. **Landing-page discoverability (closed 2026-07-13).** The docs landing
   page now leads readers to the palette (`Ctrl/Cmd-K`) instead of a static
   link list.

## Proposed next-wave shape (for the ADR/plan to ratify)

- W1: measure — run the held-out miss-rate over the current mapping; run a
  coverage sweep of legal-corpus and casilla-registry targets with no
  inbound relevance entry; inventory the synonym queue. All read-only, all
  producing committed reports.
- W2: widen — extend the query vocabulary from the coverage report
  (per-modelo casilla labels, legal-provision vocabulary from the bundled
  corpus), re-run the sweep, review diffs, commit the widened mapping.
- W3: decide rung 2 — with the miss-rate measured, take the deferred
  decision: implement the int8 term-embedding matrix only if misses are
  material, per the ADR's stated gate.
- W4: hook wiring — author the `.vaultragpreprocess.toml` rules over the
  bundled legal and modelo corpus, prove parity between hook output and
  the committed sidecars per source kind (`preprocess run-one`), then
  retire the committed sidecar tree and the stale
  `dev/docs/preprocess/__init__.py` claim in one atomic change.
