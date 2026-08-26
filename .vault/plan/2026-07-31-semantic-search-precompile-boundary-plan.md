---
tags:
  - '#plan'
  - '#semantic-search-precompile-boundary'
date: '2026-07-31'
modified: '2026-08-02'
body_hash: 'sha256:95c59d6471720eaed42722f6abad8730601f7a09dfa1c5e0ac4a5ed6a16de6c9'
tier: L2
related:
  - '[[2026-07-31-semantic-search-precompile-boundary-adr]]'
  - '[[2026-08-01-semantic-search-precompile-boundary-close-honesty-review-audit]]'
---
# `semantic-search-precompile-boundary` plan

## Description

Executes the semantic-search-precompile-boundary ADR: retire the runtime embedding stack from the shipped product so the only semantic-search artefact the project depends on remains the dev-side precompiled, laundered docs-search data. The shipped retrieval surface narrows to the FTS5 lexical index with the Spanish stemmed column, the exact citation lookup, the terminology lookup, and the command-search BM25 ranker. The `cadrumo[search]` extra, the model2vec loader, the query embedder, the corpus-vector build, and every semantic fusion path are deleted outright, with no shim, per the pre-release no-legacy discipline. The plan is deletion-heavy and crosses gated collateral surfaces (apidocs stubs, error registry, locales, harness drift gate), each retired through its owning CLI. Phase P01 is a hard precondition: uncommitted peer work is in flight on the deletion targets and must be handed off first.

## Steps

### Phase `P01` - Coordination and decision-trail truth

Hand off the in-flight loader-hardening WIP and stamp the R3 amendment so no agent hardens a surface scheduled for deletion and no reader takes the refoundation ADR's semantic half as still in force.

- [x] `P01.S01` - Report the collision between this ruling and the in-flight loader-hardening WIP to the coordinator and obtain an explicit handoff of the uncommitted changes before any deletion touches those files; `src/cadrumo/application/corpus_search/_model_loader.py`.
- [x] `P01.S02` - Annotate ruling R3 of the agent-harness-refoundation ADR as amended by the semantic-search-precompile-boundary ADR, following the existing R2 and R8 amendment-note pattern; `.vault/adr/2026-07-02-agent-harness-refoundation-adr.md`.

### Phase `P02` - Atomic rewire and deletion

One atomic explicit-pathspec commit rewires every consumer to lexical plus citation retrieval and deletes the semantic modules with their tests and apidocs stubs, so no intermediate tree state has a shipped surface importing a removed capability.

- [x] `P02.S03` - Rewire search_corpus and hybrid retrieval to lexical plus citation only, deleting the embedder wiring, vector loading, and semantic fusion, and reconcile every RetrievalMode consumer to the narrowed member set; `src/cadrumo/application/corpus_search/_runtime.py`.
- [x] `P02.S04` - Delete _model_loader.py, _query_embed.py, and _embed_build.py together with their facade exports and error-surface references; `src/cadrumo/application/corpus_search/`.
- [x] `P02.S05` - Rewire the command-search index to per-column BM25 plus token-overlap only, deleting the model2vec semantic side, the RRF fusion, and the query_embedder parameter on the meta-tools builder; `src/cadrumo/application/command_search/_index.py`.
- [x] `P02.S06` - Delete test_embed_build.py, test_query_embed.py, test_hybrid_real_model_recall.py, and test_hybrid_real_model_recall_live.py, and rewrite the semantic branches of the surviving corpus-search and command-search tests against the lexical-only shape; `src/cadrumo/application/corpus_search/tests/`.
- [x] `P02.S07` - Regenerate the apidocs stubs for the deleted modules, verify clean collect-only, and land the whole phase as one atomic explicit-pathspec commit; `docs/api/`.

### Phase `P03` - Packaging and diagnostics retirement

Remove the search extra and its dependency pins, promote the stemmer to core, and retire the dead dependency error with its registry row and locale keys through the owning CLIs.

- [x] `P03.S08` - Delete the search optional extra with its model2vec, huggingface-hub, and numpy pins, prune the all aggregate, promote snowballstemmer into the core dependency set, and refresh the lockfile; `pyproject.toml`.
- [x] `P03.S09` - Retire CorpusSearchDependencyError together with its error-registry row, and remove its locale keys through the locales CLI leaving scaffold check clean; `src/cadrumo/core/errors/registry/_application_part1.py`.
- [x] `P03.S10` - Sweep every remaining install hint naming the retired extra from production strings, the extras-reporting half of this step being vacated by ADR Update 1 because config check never named a search extra; `src/cadrumo/`.

### Phase `P04` - Surface truth sweep and verification

Make every operator-facing surface stop claiming semantic retrieval, rebuild the shippability and ranking gates around the single lexical shape, and close with the mandated fresh-context honesty review.

- [x] `P04.S11` - Sweep the MCP corpus and meta tool descriptions and docstrings to describe lexical plus citation retrieval, keeping the harness rule-surface drift gate green; `src/cadrumo/entrypoints/mcp/`.
- [x] `P04.S12` - Sweep the operator harness documents and user documentation for hybrid or semantic retrieval claims and verify the docs build gates; `docs/`.
- [x] `P04.S13` - Run the corpus-search and command-search suites sequentially plus full collect-only, and record the gate outputs in the exec records; `src/cadrumo/application/corpus_search/tests/`.
- [x] `P04.S14` - Run the fresh-context honesty review against the closure summary and persist it as a vault audit before declaring the campaign structurally complete; `.vault/audit/`.

## Parallelization

Phases are sequential: P01 gates everything (live peer WIP sits on the P02 deletion targets), P02 must land as one atomic commit before P03 removes the packaging metadata the P02 tree no longer references, and P04 sweeps surfaces whose truth depends on P02 and P03 having landed. Within P02 the steps are one work unit landing in a single explicit-pathspec commit and must not be dispatched to parallel agents. P03 steps S08 to S10 may run in parallel after P02. P04 steps S11 and S12 may run in parallel, S13 and S14 close sequentially.

## Verification

- No module under `src/cadrumo/` imports model2vec, huggingface-hub, or numpy, verified by grep over the production tree.
- `pyproject.toml` declares no `search` extra, the `all` aggregate omits it, and the PRODUCT closure (`uv tree --no-dev`) resolves without the three retired packages. Corrected 2026-08-01 per ADR Update 1: `huggingface-hub` and `numpy` legitimately remain in the lock as dev-group transitives of the vaultspec-rag oracle, so their absence from the lockfile is NOT a criterion and must not be "fixed" by removing the dev oracle.
- `search_corpus` and the command-search index return ranked results on a bare-core install with no network access. Corrected 2026-08-01 per the P04 close honesty review: the original wording claimed this was "proven by the rewritten shippability and ranking-golden tests running with sockets unavailable", but NO socket-blocking mechanism exists in those tests and none was ever built. The real and stronger proof is structural, in two parts: an AST gate walks every shipped module of both search packages (with an anti-vacuity floor refusing a collapsed walk) and refuses any import of model2vec, huggingface_hub, numpy, onnxruntime, or torch, including function-local and TYPE_CHECKING imports a runtime socket blocker would miss; and the retrieval, lexical-index, and ranking-golden tests then produce ranked results from exactly those modules. No production search module can reach the network because none imports a client, which is a compile-visible guarantee rather than a per-test runtime one. The criterion stands; only its stated mechanism was wrong.
- The full suite collects cleanly and the corpus-search, command-search, and MCP test trees pass sequentially.
- `python -m dev.docs.apidocs scaffold --check` exits clean, the docs build gates pass, and the harness rule-surface drift gate passes.
- No production string, tool description, harness document, or user doc references the retired extra or claims semantic or hybrid retrieval.
- The fresh-context honesty review audit exists in the vault and its surfaced items are closed or formally deferred before the campaign is declared complete.
