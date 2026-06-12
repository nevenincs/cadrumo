---
name: shipped-search-licence-clean
---

# Shipped Search Licence Clean

## Rule

Documentation search artifacts that ship in the package or built docs must contain only licence-clean sources and laundered identifiers/rankings; never ship vectors, sparse term weights, raw retrieval scores, snippets, or data derived from NC/ND/gated sources.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` makes licence-clean shipping a hard constraint and, in D6/D9, allows the dev RAG only as a build-time oracle whose outputs are laundered before shipping. This prevents SPLADE or other restricted model/data outputs from tainting the offline documentation search backend.

## How

- Good: Commit a relevance mapping containing target ids, target URLs, surfaces, and normalised ranking weights after ratified review.
- Bad: Commit an embedding vector, SPLADE sparse map, raw score/path/snippet payload, or unreviewed term data from an NC, ND, gated, or unlicensed source.
