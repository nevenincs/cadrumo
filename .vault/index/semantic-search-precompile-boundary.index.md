---
generated: true
tags:
  - '#index'
  - '#semantic-search-precompile-boundary'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:d1e9c8e42ae45a6c1c34f3313fd47b8f03d94db51b061c938e03d6bde849c6db'
related:
  - '[[2026-07-31-semantic-search-precompile-boundary-P01-S01]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P01-S02]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P02-S03]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P02-S04]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P02-S05]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P02-S06]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P02-S07]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P03-S08]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P03-S09]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P03-S10]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P04-S11]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P04-S12]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P04-S13]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-P04-S14]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-adr]]'
  - '[[2026-07-31-semantic-search-precompile-boundary-plan]]'
  - '[[2026-08-01-semantic-search-precompile-boundary-close-honesty-review-audit]]'
---

# `semantic-search-precompile-boundary` feature index

Auto-generated index of all documents tagged with `#semantic-search-precompile-boundary`.

## Documents

### adr

- `2026-07-31-semantic-search-precompile-boundary-adr` - `semantic-search-precompile-boundary` adr: `semantic search is a precompile step: retire the runtime embedding stack` | (**status:** `accepted`)

### audit

- `2026-08-01-semantic-search-precompile-boundary-close-honesty-review-audit` - `semantic-search-precompile-boundary` audit: `campaign close honesty review`

### exec

- `2026-07-31-semantic-search-precompile-boundary-P01-S01` - Report the collision between this ruling and the in-flight loader-hardening WIP to the coordinator and obtain an explicit handoff of the uncommitted changes before any deletion touches those files
- `2026-07-31-semantic-search-precompile-boundary-P01-S02` - Annotate ruling R3 of the agent-harness-refoundation ADR as amended by the semantic-search-precompile-boundary ADR, following the existing R2 and R8 amendment-note pattern
- `2026-07-31-semantic-search-precompile-boundary-P02-S03` - Rewire search_corpus and hybrid retrieval to lexical plus citation only, deleting the embedder wiring, vector loading, and semantic fusion, and reconcile every RetrievalMode consumer to the narrowed member set
- `2026-07-31-semantic-search-precompile-boundary-P02-S04` - Delete _model_loader.py, _query_embed.py, and _embed_build.py together with their facade exports and error-surface references
- `2026-07-31-semantic-search-precompile-boundary-P02-S05` - Rewire the command-search index to per-column BM25 plus token-overlap only, deleting the model2vec semantic side, the RRF fusion, and the query_embedder parameter on the meta-tools builder
- `2026-07-31-semantic-search-precompile-boundary-P02-S06` - Delete test_embed_build.py, test_query_embed.py, test_hybrid_real_model_recall.py, and test_hybrid_real_model_recall_live.py, and rewrite the semantic branches of the surviving corpus-search and command-search tests against the lexical-only shape
- `2026-07-31-semantic-search-precompile-boundary-P02-S07` - Regenerate the apidocs stubs for the deleted modules, verify clean collect-only, and land the whole phase as one atomic explicit-pathspec commit
- `2026-07-31-semantic-search-precompile-boundary-P03-S08` - Delete the search optional extra with its model2vec, huggingface-hub, and numpy pins, prune the all aggregate, promote snowballstemmer into the core dependency set, and refresh the lockfile
- `2026-07-31-semantic-search-precompile-boundary-P03-S09` - Retire CorpusSearchDependencyError together with its error-registry row, and remove its locale keys through the locales CLI leaving scaffold check clean
- `2026-07-31-semantic-search-precompile-boundary-P03-S10` - Sweep every remaining install hint naming the retired extra from production strings, the extras-reporting half of this step being vacated by ADR Update 1 because config check never named a search extra
- `2026-07-31-semantic-search-precompile-boundary-P04-S11` - Sweep the MCP corpus and meta tool descriptions and docstrings to describe lexical plus citation retrieval, keeping the harness rule-surface drift gate green
- `2026-07-31-semantic-search-precompile-boundary-P04-S12` - Sweep the operator harness documents and user documentation for hybrid or semantic retrieval claims and verify the docs build gates
- `2026-07-31-semantic-search-precompile-boundary-P04-S13` - Run the corpus-search and command-search suites sequentially plus full collect-only, and record the gate outputs in the exec records
- `2026-07-31-semantic-search-precompile-boundary-P04-S14` - Run the fresh-context honesty review against the closure summary and persist it as a vault audit before declaring the campaign structurally complete

### plan

- `2026-07-31-semantic-search-precompile-boundary-plan` - `semantic-search-precompile-boundary` plan
