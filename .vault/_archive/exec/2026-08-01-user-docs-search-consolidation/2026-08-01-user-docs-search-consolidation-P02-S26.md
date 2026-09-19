---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2dba36eda264e5830ec6d55c4bcef85eb6b6c9bb5e87a6544304874bc7215bee'
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

### 2026-08-06 authorized provider and raw-byte evidence

Fresh vaultspec-rag grounding of the manifest-role audit, accepted ADR Update 8, and the P02.S26 source contract returned request 4d76532849294564b1df4b60167d3297. The authorized temporary provider lane now supplies the real independent evidence that the source-only record previously lacked: provider-source, model-snapshot, tokenizer-vocabulary, and tokenizer-configuration manifests were verified against local raw bytes and their independent roots.

The verified evidence identifies model2vec 0.8.2, provider revision c90140706ed2162c75c6f004b66e37a342fd8f1a, Potion revision e7421cd79c75fc506b88bb75723ae0a234994720, model snapshot root 869266e7140deabcaa3e5e0e69c7e017af5507d07006114690fb05d3ab06c9d6, provider-source root 581adaf84f2b25e40a2b930852c5ac65223166b02cc31126ca8267450d20dcef, tokenizer-configuration root ca3339ad4370f46cf5189c54a3cbac46e13f0639e66cf173a2ebe07f2ce86ede, and tokenizer-vocabulary root 16d9434a6dba49dffd2a831ceb73bcbab2662b32d7bd3d0c4a2544e3b4c22d3b. The model snapshot and tokenizer role projections are contained and disjoint under the source contract.

The installed-provider verification was executed against the local verified roots and manifests with the production PotionModel2VecProvider; it returned provider_version 0.8.2, model_revision e7421cd79c75fc506b88bb75723ae0a234994720, dimension 256, and bundle SHA f220aa7876b2d77dade0d7710b6b6456204ba4717148f73c66aeb6aac7f6be19. This satisfies the previously open P02.S26 evidence boundary. It does not accept the Rung-2 bundle or enable the browser: P02.S04, P02.S05, P02.S06, P02.S07, P02.S25, locale/kind parity, and deployment remain independently gated.

### 2026-08-06 LUNA MAX provider-boundary remediation and verification

Fresh vaultspec-rag grounding over the accepted provider contract, P02.S26 evidence, and the current provider source confirmed the selected `model2vec==0.8.2` lane. The live code search shows the production adapter loads the reviewed local snapshot with `force_download=False` and embeds with `use_multiprocessing=False`; the LUNA MAX remediation additionally derives the `[UNK]` identity from the tokenizer and rejects a missing, invalid, or negative tokenizer id before embedding. This closes the previously reviewed conditional unknown-token boundary without changing the pinned model, manifest schema, or browser contract.

Authorized focused real-behaviour verification returned `67 passed in 20.84s` across the static-matrix, provider-boundary consumers, acceptance, evaluator, report, provenance, input, and query-authority suites. Ruff, basedpyright (`0 errors, 0 warnings, 0 notes`), `node --check docs/_static/cadrumo-docs.js`, and scoped `git diff --check` also passed. The documented RAG CLI lane was used because the MCP `codebase` alias remains rejected as `unknown_source_type`.

The verified provider/model evidence and the rejected standing Rung-2 report remain unchanged: the bundle is not promoted or enabled, no deployment was performed, and shared-worktree peer WIP was preserved.
