# Shipped search artefacts are licence-clean

Documentation search artefacts that ship in the package or the built docs must
come only from licence-clean sources and contain only laundered identifiers and
rankings. **Never ship** anything derived from NC, ND or gated sources; raw
oracle output (raw retrieval scores, snippets, sparse maps, sparse term weights);
or raw or unbounded vectors.

**The sole narrow embedding exception:** a bounded term-embedding matrix may ship
**in the built docs, never in the wheel**, only when it is reviewable plain data
computed on the dev box by a pinned, named model under the MIT or Apache-2.0
licence over project-authored or project-bundled vocabulary. Its provenance stamp
must name the model, exact revision, licence, vocabulary fingerprint and
serialized size, and the matrix must be no larger than 3 MB.

**Commit only the LIGHT precompiled data** — the laundered relevance mapping,
synonym candidates, held-out queries, the Handbook fragments, and any qualifying
matrix. **Never commit the HEAVY generated search index** (the Pagefind corpus and
the docs build output), which is gitignored and regenerated on every docs build.

The dev RAG is a build-time oracle only, and its outputs are laundered before
shipping. The commit boundary exists because a compiled index of tens of
thousands of files was once committed at the repo root: the index is a
deterministic build output, not source, so committing it bloats every clone and
drifts from the corpus. The light data is what CI and readers consume; the heavy
index they regenerate.

## How

- **Good:** commit a relevance mapping of target ids, URLs, surfaces and
  normalised ranking weights after ratified review; keep the generated index
  gitignored and untracked, and regenerate it at docs-build time.
- **Bad:** committing an embedding vector or matrix outside the narrow exception;
  committing sparse maps or raw score, path or snippet payloads; committing
  unreviewed term data from an NC, ND, gated or unlicensed source; or committing
  the generated index corpus.

Source: ADRs `2026-06-10-docs-terminology-search-adr` (D6, D9),
`2026-08-01-user-docs-search-consolidation-adr` (R5),
`2026-06-15-docs-terminology-search-adr` (D3).
