---
tags:
  - '#audit'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:585d38793d4be6b7b8a15f491e36068106e037f5dffc03c9c20e55763757996f'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-01-user-docs-search-consolidation-P02-S26]]"
  - "[[2026-08-05-user-docs-search-consolidation-source-implementation-audit]]"
---
# `user-docs-search-consolidation` audit: `Audit the Rung-2 manifest role disjointness correction`

## Scope

Mandatory LUNA EXTRA HIGH read-only review of exactly the eight-line uncommitted hunk in `dev/docs/terminology/_model2vec_provider.py` that projects the supplied tokenizer-vocabulary and tokenizer-configuration manifest entries to path sets and rejects their intersection with `MatrixCompilationError`. The review began with fresh vaultspec-rag code and vault searches for the raw-byte manifest role contract, then read the active plan, ADR Update 8, the P02.S26 execution record, the source implementation audit, `dev/docs/terminology/_content_manifest.py`, and `dev/docs/terminology/_model2vec_provider.py` in full. Peer WIP was preserved and no source file was edited.

Review verdict: PASS for the bounded implementation correction. P02.S26 remains OPEN for the separately required real provider-package/model/tokenizer manifests, installed-version evidence, matrix generation, quantization, and held-out acceptance evidence. No tests, builds, model downloads, generation, probes, reindexing, or deployment were run.

## Findings

### manifest-role-disjointness | low | PASS: tokenizer projections are disjoint and snapshot-contained

The accepted Update 8 contract requires a complete `model-snapshot` manifest and reviewed vocabulary/configuration projections from that snapshot. In `_model2vec_provider.py:238-270`, the model manifest is verified first with the strict default `reject_unexpected=True`; each tokenizer projection is verified against the same local model root with its declared role, repository, revision, root hash, and raw bytes. The hunk at `_model2vec_provider.py:271-278` computes only the already-supplied manifest-entry path sets and rejects a non-empty intersection. The existing containment loop at `_model2vec_provider.py:279-287` then requires every tokenizer entry to match a model-snapshot entry by exact relative path, byte length, and SHA-256. This matches the Sol-medium interpretation: the model snapshot is the complete containment authority, while the two tokenizer role projections must be disjoint.

### fail-closed-ordering | low | PASS: validation ordering and error boundary are preserved

Provider, model-snapshot, and tokenizer role identity/root/local-byte validation still precede the new structural check, and the overlap error is raised before the existing tokenizer-to-snapshot containment loop and long before installed-package lookup, optional provider import, or `from_pretrained`. A collision therefore cannot reach model loading, while invalid role metadata or invalid local evidence retains the earlier, more specific manifest error. The new error is a deterministic `MatrixCompilationError` with sorted offending paths.

### strictness-and-surface | low | PASS: no discovery, schema invention, or typing/style regression

The hunk performs no filesystem walk, filename inference, download, or provider call; it projects explicit `RawByteManifest.entries` only. It adds no manifest field, schema version, compatibility path, or relaxed verification mode. The strict/frozen manifest contracts and explicit-path builder in `_content_manifest.py:43-150`, the strict local verifier in `_content_manifest.py:152-174`, and the existing role/snapshot checks remain unchanged. The added expressions infer `set[str]` from typed entries, stay within the configured 120-character line limit, and preserve the existing import/style surface. `git diff --check`, Ruff, and basedpyright passed for the touched provider module.

### acceptance-boundary | low | OPEN: source PASS does not close P02.S26

The plan and P02.S26 execution record correctly keep the step open until reviewed local manifests, installed provider evidence, the pinned model snapshot, matrix generation, and acceptance measurements exist. This review observed none of those runtime/artifact inputs and closes no plan or acceptance row.

## Recommendations

- Retain the bounded hunk as the source-level role-disjointness correction; do not add filename conventions or schema fields in this review.
- Close P02.S26 only after the authorized real manifests and provider/model/tokenizer and matrix acceptance evidence are supplied and independently verified under Update 8.
