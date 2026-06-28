---
tags:
  - '#research'
  - '#vaultspec-rag-ignore-rebuild'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-01-semantic-cluster-hardening-audit]]'
---

# `vaultspec-rag-ignore-rebuild` research: `VaultSpec RAG ignore scope before rebuild`

This research scoped what should be excluded from the VaultSpec RAG semantic code index before the required package update and full rebuild.

## Findings

The installed RAG CLI documents `.vaultragignore` as the persistent code-index ignore file. It is combined with command-line `--exclude` patterns, while `.gitignore` remains an independent pruning source in the code indexer.

The repository already excludes build outputs and local runtime state in `.gitignore`, including `docs/_build`, `docs/cli`, virtual environments, caches, scratch output, and `.vault/data`. The RAG-specific ignore should therefore focus on text that is either generated, duplicated, or low-signal for vector research.

Hand-written documentation under `docs` should remain indexable. It contains user-facing explanations, how-to material, architecture context, and glossary language that complements code and vault records. Excluding the whole `docs` tree would remove useful retrieval vocabulary for operator workflows.

Generated documentation should be excluded. `docs/api` duplicates source docstrings and module structure, while `docs/_build` and `docs/cli` are build-time outputs. Keeping them in the semantic index increases duplicate chunks and stale-result risk without adding durable context.

Generated provider rule and skill copies should be excluded. `.agents`, `.claude`, `.codex`, `.gemini`, `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` repeat VaultSpec-managed source material and crowd search results with provider variants. The source rule/skill material remains available through the project files and active runtime instructions, while the duplicated generated copies do not need vector indexing.
