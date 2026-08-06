---
tags:
  - '#reference'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:be076ef3a836bdedd008b514ae42b20d10860a6ea953a7a540f632e9d36c27b9'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-deterministic-casilla-enrollment-research]]"
  - "[[2026-08-05-user-docs-search-consolidation-p02-s04-query-token-matrix-audit]]"
---

# `user-docs-search-consolidation` reference: source contract blueprint

## Summary

The RAG-grounded source implementation separates deterministic user-document enrollment from semantic relevance. Registry-backed casilla projection is exhaustive and typed; an explicit `modelo` plus `casilla` query resolves through structured metadata before lexical fallback. Sparse relevance mappings and the future Rung-2 semantic tier are additive matching layers, not authorities for whether a casilla exists or what it means.

## Deterministic casilla surface

`dev/docs/terminology/_casilla_projection.py` derives the casilla universe from the validated registry and carries localized labels, help, input kind, data type, requiredness, binding, and formula metadata. `dev/docs/terminology/_unified_record.py` preserves those typed fields while keeping the opaque search identity separate. `docs/_static/cadrumo-docs.js` recognizes structured modelo/casilla forms and resolves the canonical record and target before the Pagefind compose ladder. `dev/docs/terminology/_resolution.py` resolves relevance hits only when their source range identifies one casilla section; ambiguous or file-level fallback is refused.

The generated casilla reference renderer and the projection share the destination authority. The M130/casilla-15 path is source-covered by the registry, projection, exact route, localized definition checks, and target checks, but the plan's P06.S24 real-behaviour gate remains open because no build, browser probe, or test execution has been authorized.

## Legal record surface

`dev/docs/legal_reference.py` owns generated legal page slugs and provision anchors from the registry catalogue. `dev/docs/terminology/_legal_projection.py` projects each provision into the dedicated `LEGAL` record kind, preserving BOE provenance as metadata while using the generated site-relative target for search. `dev/docs/pagefind_inject.py` injects the typed record beside the other decided kinds. The source-level legal resolver requires a named provision and refuses unknown or ambiguous targets. P05.S14 through P05.S17 remain open for generated-surface and parity-gate evidence.

## Rung-2 source boundary

`dev/docs/terminology/_static_matrix.py` owns canonical vocabulary/query-token identity, float32 and symmetric per-row int8 contracts, model/tokenizer provenance, and the shared serialized-size bound. `dev/docs/terminology/_model2vec_provider.py` accepts only an already-present local Potion Model2Vec directory and validates the ratified repository, immutable revision, MIT licence, dimension, and installed package boundary; it does not download a model. `_rung2_inputs.py` binds the future compiler to the committed relevance sweep and authoritative unified-record projection. `_rung2_bridge.py` links the matrix to manifest records and their targets. `_rung2_compiler.py` composes those contracts, while `_rung2_acceptance.py` and the browser reader fail closed unless measured acceptance evidence and a hash-linked bundle are supplied.

The source seam is intentionally not a shipped semantic tier yet. No provider artifact, generated matrix, measured quantisation drift, held-out acceptance result, Pagefind build, browser runtime, or release configuration exists. The approved ADR therefore keeps the browser semantic tier disabled and Pagefind/lexical search authoritative until those evidence gates are separately accepted.

### Cross-runtime canonical JSON vector boundary

The accepted ADR Update 10 defines `cadrumo-jcs-utf8-lf-v1` as the single Python/browser byte contract: recursively UTF-16-sorted object keys, ECMAScript/JCS number spelling, strict UTF-8, and exactly one terminal LF. A language-neutral corpus and independent consumers now live under `dev/docs/terminology/jcs_vectors/`; the Python consumer imports `canonical_json_bytes` directly and the JavaScript consumer does not invoke Python. Static JSON parsing, Ruff, basedpyright, `node --check`, and `git diff --check` pass for this new source slice. The consumers have not been executed, so P02.S25 remains an evidence-gated open step and no Rung-2 artifact or browser enablement is implied.

## Verification boundary

The current source evidence is vaultspec-rag discovery, targeted source reading, static typing/lint/syntax/diff checks, and formal review. Tests, builds, model downloads, matrix generation, Pagefind/runtime probes, live RAG sweeps, reindexing, deployment, and generated-artifact release remain deferred by instruction. Consequently the VaultSpec plan remains at 12 of 28 steps closed, with P02.S04 as the next open step; source presence must not be reported as shipped-site acceptance.
