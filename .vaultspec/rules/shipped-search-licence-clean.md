---
name: shipped-search-licence-clean
---

# Shipped Search Licence Clean

## Rule

Documentation search artifacts that ship in the package or built docs must contain only licence-clean sources and laundered identifiers/rankings; never ship vectors, sparse term weights, raw retrieval scores, snippets, or data derived from NC/ND/gated sources. Commit only the LIGHT precompiled DATA (the laundered relevance mapping, synonym candidates, held-out queries, the Handbook fragments); never commit the HEAVY generated search INDEX (the Pagefind corpus under `pagefind/` and `docs/_build/`), which is gitignored and regenerated on every docs build.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` makes licence-clean shipping a hard constraint and, in D6/D9, allows the dev RAG only as a build-time oracle whose outputs are laundered before shipping. This prevents SPLADE or other restricted model/data outputs from tainting the offline documentation search backend. The `2026-06-15-docs-terminology-search-adr` (D3) adds the commit boundary after a 63 MB / ~16k-file compiled Pagefind index was found committed at the repo root: the index is a deterministic build output, not source, so committing it bloats every clone and drifts from the corpus. The light precompiled data is what CI and readers consume; the heavy index they regenerate.

## How

- Good: Commit a relevance mapping containing target ids, target URLs, surfaces, and normalised ranking weights after ratified review; keep `pagefind/` gitignored and untracked.
- Good: regenerate the Pagefind index at docs-build/deploy time from the committed light data; never `git add` the generated `pagefind/` corpus.
- Bad: Commit an embedding vector, SPLADE sparse map, raw score/path/snippet payload, or unreviewed term data from an NC, ND, gated, or unlicensed source.
- Bad: commit the generated Pagefind index corpus (`pagefind/`, thousands of fragment/index/wasm files) to the git base.
