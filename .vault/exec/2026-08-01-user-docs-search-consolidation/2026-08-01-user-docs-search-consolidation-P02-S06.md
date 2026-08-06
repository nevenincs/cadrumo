---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:6c8dd0d519e8bf4b62879c760c97fca099a3f858025c0b3a75e90d838fc9b253'
step_id: 'S06'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Extend the licence gate to validate the shipped matrix's provenance stamp, model licence, and size bound while keeping every oracle-output and NC-ND bar intact

## Scope

- `dev/docs/tests/`

## Description

## Description

- Re-ground P02.S06 with current vaultspec-rag searches over the Rung-2 acceptance, bundle, matrix, provider, and content-manifest source seams, plus the accepted consolidation ADR updates.
- Inspect the current source-only contract without running tests, builds, model downloads, artifact generation, runtime probes, live sweeps, reindexing, or deployment.
- Record whether the licence/provenance/size gate is absent, incomplete, or present but evidence-gated.

## Outcome

## Outcome

The source-side P02.S06 contract is present. The acceptance boundary validates canonical bundle bytes and SHA-256 identity, the shared serialized-byte bound, embedded input-provenance fingerprints, and the ratified model repository, immutable revision, SPDX licence, and dimension. The matrix schema restricts the accepted licence set, while the provider requires raw-byte manifests for provider, model, and tokenizer roles before importing the optional provider or loading model content.

No shipped matrix, real provider/package/model/tokenizer manifests, measured quantization evidence, or held-out acceptance evidence is present. P02.S06 therefore remains unchecked: this record establishes source readiness, not licence-gate or artifact acceptance.

## Notes

### 2026-08-05 source contract correction

Fresh `vaultspec-rag` grounding and exact production/test reads identified a stale acceptance fixture: `dev/docs/terminology/tests/test_rung2_acceptance.py` supplied the retired Rung-2 config schema literal `cadrumo.docs-search.rung2-config.v1` while the production acceptance model and browser contract require the exported `RUNG2_CONFIG_SCHEMA_VERSION` v2 constant. The LUNA Max worker changed only that fixture to import and use the production constant. The LUNA Extra High review returned PASS; its only finding was LOW and non-blocking: no dedicated assertion independently rejects retired v1, while production validation remains strict.

No tests, builds, runtime probes, artifact generation, downloads, live sweeps, reindexing, or deployment were run. P02.S06 remains open because real matrix/provider/licence evidence and authorized acceptance gates are still absent.

### 2026-08-05 LUNA Max acceptance/manifest review

Fresh vaultspec-rag grounding and exact source review by the delegated LUNA Max worker found no concrete defect in `_rung2_acceptance.py` or `_content_manifest.py`. The acceptance boundary validates the exact bundle bytes, shared size bound, input-provenance fingerprints, ratified model identity/licence/dimension, and shared normalization; the manifest contract verifies explicit local raw bytes, roles, revisions, hashes, path safety, and unexpected-file policy. No files were edited.

Ruff, basedpyright (0 errors, 0 warnings, 0 notes), AST parsing, and targeted `git diff --check` passed. No tests, builds, downloads, matrix or manifest generation, runtime probes, sweeps, reindexing, deployment, or other paths were touched. P02.S06 remains open for real evidence and authorized acceptance gates.

### 2026-08-06 authorized contract gates

`uv run --no-sync pytest -q -m "unit or (integration and not serial)" -n0 dev/docs/terminology/tests/test_rung2_acceptance.py dev/docs/terminology/tests/test_rung2_provenance.py dev/docs/terminology/tests/test_static_matrix_contract.py` returned `33 passed in 1.05s`. These are real production-model contract checks; they do not constitute provider licensing, browser configuration, held-out recall, or release acceptance. P02.S06 remains open until those measured gates are evidenced against the accepted artifact.

## Notes

- No tests, builds, model downloads, generated artifacts, Pagefind/runtime probes, live sweeps, RAG reindexing, or deployment were run.
- No source file was changed in this tranche; concurrent shared-worktree changes were preserved.
- Closure requires real manifest and provider evidence plus the authorized acceptance gates; the standing no-tests boundary remains in force.
