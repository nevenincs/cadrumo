---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:9c39d1778a9d2489376f7764e22032d325a1225ea3db59d55977ca74c2acd79f'
related: []
---

# `user-docs-search-consolidation` audit: `P03.S09 fresh-context honesty review`

## Scope

Perform a fresh-context honesty review of the UserDocs Search consolidation after the P03.S18 residue sweep. Ground the review with `vaultspec-rag` searches over the active plan, accepted ADR, research, execution records, and source implementation, then confirm the candidate surfaces against current files and Git history. The review is intentionally source-only: deployment, builds, tests, browser probes, live RAG sweeps, model generation, runtime gates, and deployment remain outside the authorized boundary.

## Findings

### rung2-source-boundary | medium | Rung 2 is not yet an artifact-backed searchable tier

The RAG-grounded plan still requires a pinned licence-clean provider, a real bounded matrix artifact, a browser query-encoding contract, a stable bridge from semantic terms to injected `SearchRecord` ids, a client cosine tier, licence/size gates, and a new held-out baseline. Current `dev/docs/terminology/_static_matrix.py` is a model-agnostic schema/compiler seam (now schema v2 with separate query-token rows); it deliberately has no selected provider, tokenizer contract, generated artifact, browser reader, or measured thresholds. P02.S04 through P02.S07 therefore remain open. Adding a browser scorer before those contracts are ratified would invent product semantics.

### legal-source-boundary | low | Legal search source seams are present but acceptance is unrun

RAG and source inspection confirm that the legal projection emits dedicated `LEGAL` records, renderer-owned page/anchor targets, and typed BOE provenance; the injector includes those records in the shared index and the parity/target gates are present. This is source evidence, not proof of a built or searchable legal artifact: P05.S14 through P05.S17 remain open until their authorized build/index/parity gates run.

### casilla-source-boundary | low | Deterministic casilla enrollment is implemented but unexecuted

The registry-backed projection and structured search path carry the authoritative definition metadata, and the M130/casilla-15 real-behaviour gate exists. The gate has not been run under the current no-test instruction, so P06.S24 remains open; sparse relevance coverage must not be conflated with exact enrollment.

### multilingual-runtime-boundary | medium | Built and deployed language recall is unproven

P03.S08 remains open because no built-site or deployed-root probes were authorized. P04.S12 and P04.S13 also remain open; the previously recorded localized live-root failure is not silently reclassified as fixed by source changes.

### grounding-route-boundary | low | The rejected codebase alias remains an infrastructure issue

The `vaultspec-rag` codebase alias still rejects with `unknown_source_type`. The review used the working CLI code-search route and VaultSpec semantic search, without bypassing or weakening the failing alias contract. This does not invalidate the source findings, but it remains an explicit tooling limitation.

## Recommendations

- Keep P02.S04 through P02.S07, P03.S08, P04.S12 through P04.S13, P05.S14 through P05.S17, and P06.S24 open until their stated artifacts and runtime gates are authorized and observed.
- Amend the accepted consolidation ADR before coding the Rung-2 provider or browser tier, specifying model/revision/licence/configuration, tokenizer and normalization, partial-coverage abstention, the stable result bridge, ranking thresholds, and quantization acceptance.
- Treat the legal and casilla source implementations as ready for their deferred gates, not as deployment or campaign-completion evidence.
- No source remediation is opened by this honesty review; P03.S18 already records the residue sweep and found no active duplicate search implementation.
