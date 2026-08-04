---
name: shipped-search-licence-clean
trigger: always_on
---

# Shipped Search Licence Clean

## Rule

Documentation search artefacts that ship in the package or built docs must come only from licence-clean sources and contain only laundered identifiers/rankings, except for the sole narrow embedding allowance below. Never ship anything derived from NC/ND/gated sources, raw oracle output (raw retrieval scores, snippets, sparse maps, or sparse term weights), or raw or unbounded vectors. The sole narrow embedding exception is a bounded term-embedding matrix that may ship in the built docs, never in the wheel, only when it is reviewable plain data computed on the dev box by a pinned, named model under the MIT or Apache-2.0 licence over project-authored or project-bundled vocabulary. Its provenance stamp must name the model, exact revision, licence, vocabulary fingerprint, and serialized size; the matrix must be no larger than 3 MB, the upper bound of the governing 1–3 MB envelope. Commit only the LIGHT precompiled DATA (the laundered relevance mapping, synonym candidates, held-out queries, the Handbook fragments, and any qualifying matrix); never commit the HEAVY generated search INDEX (the Pagefind corpus under `pagefind/` and `docs/_build/`), which is gitignored and regenerated on every docs build.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` makes licence-clean shipping a hard constraint and, in D6/D9, allows the dev RAG only as a build-time oracle whose outputs are laundered before shipping. The accepted `2026-08-01-user-docs-search-consolidation-adr` R5 resolves the later rung-2 contradiction narrowly: a pinned, named MIT or Apache-2.0 model may produce one bounded, provenance-stamped, reviewable plain-data matrix over project vocabulary for the built docs, never the wheel. That does not relax the NC/ND/gated-source bar or permit raw scores, snippets, sparse maps, or raw oracle vectors. The `2026-06-15-docs-terminology-search-adr` (D3) adds the commit boundary after a 63 MB / ~16k-file compiled Pagefind index was found committed at the repo root: the index is a deterministic build output, not source, so committing it bloats every clone and drifts from the corpus. The light precompiled data is what CI and readers consume; the heavy index they regenerate.

## How

- Good: Commit a relevance mapping containing target ids, target URLs, surfaces, and normalised ranking weights after ratified review; keep `pagefind/` gitignored and untracked.
- Good: Commit a qualifying term-embedding matrix only as reviewable plain data no larger than 3 MB, with a provenance stamp carrying the pinned model name and exact revision, MIT or Apache-2.0 licence, project-authored or project-bundled vocabulary fingerprint, and serialized size; ship it in built docs only, never in the wheel.
- Good: regenerate the Pagefind index at docs-build/deploy time from the committed light data; never `git add` the generated `pagefind/` corpus.
- Bad: Commit an embedding vector or matrix outside the narrow pinned-model, project-vocabulary, provenance, plain-data, and 3 MB bound; or commit SPLADE/sparse maps, raw score/path/snippet payloads, or unreviewed term data from an NC, ND, gated, or unlicensed source.
- Bad: commit the generated Pagefind index corpus (`pagefind/`, thousands of fragment/index/wasm files) to the git base.
