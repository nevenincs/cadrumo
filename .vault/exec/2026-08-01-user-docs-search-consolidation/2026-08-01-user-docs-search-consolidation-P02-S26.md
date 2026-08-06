---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:613ada5538ba8eb1c7c1acc137100f5a627e5c091072570faf2e700c0ff2dc31'
step_id: 'S26'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-05-user-docs-search-consolidation-source-contract-reference]]"
  - "[[2026-08-05-user-docs-search-consolidation-source-implementation-audit]]"
---

# Implement and review Rung-2 raw-byte content attestation

## Scope

- `dev/docs/terminology/_model2vec_provider.py and the accepted ADR/schema`

## Description

- Re-ground the source boundary with vaultspec-rag against ADR Update 8, the active plan, the source contract reference, and the source implementation audit.
- Inspect the committed P02.S26 objects `a0dc2c47bf` and `351d3cb935` rather than the concurrent working-tree view.
- Persist the mandated source review after the reviewer returned PASS.

## Outcome

The source implementation now provides `RawByteManifestV1` with exact raw-byte SHA-256 evidence, canonical root hashing, reviewed role membership, path and symlink rejection, local missing/changed/unexpected-file refusal, and provider-before-import verification. Model snapshot, provider, tokenizer, metadata, and browser provenance are linked by the accepted contract. The committed-object review returned PASS and is recorded in the source implementation audit.

This closes the source-only implementation/review tranche, not the plan step. Real provider/package/model/tokenizer manifests, installed-version evidence, matrix generation, quantization and held-out measurements are still required before P02.S26 or any Rung-2 acceptance row can close.

## Notes

No tests, builds, model downloads, manifest generation, matrix generation, artifact release, Pagefind/runtime probes, live sweeps, reindexing, or deployment were run. Concurrent shared-worktree changes were not cleaned, reset, staged broadly, or incorporated.

### 2026-08-05 source continuation: shared canonical manifest bytes

The raw-byte manifest implementation now delegates both its self-attesting root digest and complete-envelope bytes to the shared `cadrumo-jcs-utf8-lf-v1` canonicalizer. This removes the second Python serializer from the provider/tokenizer attestation path and aligns P02.S26 with ADR Update 10's cross-runtime hash contract. It does not create manifest evidence or authorize provider/model use.

Static evidence only: post-edit vaultspec-rag search, Python AST parsing, and focused diff whitespace validation passed. No tests, builds, model downloads, manifest or matrix generation, runtime probes, sweeps, reindexing, deployment, or artifact release were run.

### 2026-08-05 current provider-attestation re-audit

Fresh vaultspec-rag grounding and exact source inspection confirm that the provider boundary verifies provider, model-snapshot, tokenizer-vocabulary, and tokenizer-configuration manifests before importing `model2vec` or loading the local model; it binds the pinned repository, revision, licence, package version, model dimension, manifest roots, and tokenizer entries to the accepted provenance contract. The shared canonical JCS bytes now cover the manifest envelope and root hash.

P02.S26 remains open for the evidence that source cannot manufacture: reviewed local raw-byte manifests, installed provider-version evidence, the pinned model snapshot, and the resulting matrix/acceptance measurements. No tests, builds, model downloads, manifest or matrix generation, runtime probes, sweeps, reindexing, deployment, or artifact release were run.

### 2026-08-05 tokenizer-role disjointness correction

Fresh `vaultspec-rag` grounding and Sol-medium architecture adjudication identified a concrete gap in the raw-byte manifest contract: the complete `model-snapshot` manifest must contain tokenizer files, while the `tokenizer-vocabulary` and `tokenizer-configuration` role projections must not overlap. The provider previously checked only exact snapshot containment. The LUNA Max worker added a fail-closed intersection check in `_verify_content_manifests` that rejects any path present in both tokenizer role manifests without inventing filenames or changing the schema.

The LUNA Extra High review returned PASS with no findings for the exact hunk. P02.S26 remains open for real provider/package/model/tokenizer manifests, installed-version evidence, matrix generation, and measured acceptance. No tests, builds, model downloads, manifest or matrix generation, runtime probes, sweeps, reindexing, deployment, or artifact release were run.

### 2026-08-05 LUNA Extra High provider review

Read-only LUNA Extra High review, grounded with vaultspec-rag and exact current source, found two open provider-boundary defects in the peer WIP: unknown-token rejection is conditional when `unk_token_id` is absent (MEDIUM), and provider-source manifest revision is not bound to the pinned provenance (MEDIUM). The peer-owned `_model2vec_provider.py` was not edited. P02.S26 remains open for remediation and independent provider evidence; no model/package/artifact gate was run.
