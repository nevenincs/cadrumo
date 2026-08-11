---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:e64c291efee58f0e918f1792e9024270fadb05a6812d7045e2dfee4442d60fa1'
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

### 2026-08-07 focused contract verification after matrix commit

The bounded real-behaviour Rung-2 suite ran against the current shared tree and committed matrix: `uv run --no-sync pytest -q dev/docs/terminology/tests/test_rung2_acceptance.py dev/docs/terminology/tests/test_rung2_evaluation.py dev/docs/terminology/tests/test_rung2_inputs.py dev/docs/terminology/tests/test_rung2_query_authority.py dev/docs/terminology/tests/test_rung2_report.py dev/docs/terminology/tests/test_sweep.py` returned `83 passed in 46.79s`.

This verifies the source contracts, provider/provenance validation shape, input assembly, report/evaluation seams, alias authority, and sweep laundering. It does not satisfy P02.S06 acceptance: the exact full bundle remains temporary, semantic evidence remains diagnostic at 22/32 hits and `0.3125` miss-rate with `93/123` token coverage (`0.7560975609756098`), and accepted quantization, full-ladder, locale/kind parity, and browser-config evidence are still absent. No threshold was relaxed and the browser tier remains fail-closed.

### 2026-08-07 LUNA Extra-High acceptance review

A separately delegated LUNA Extra-High review grounded the P02.S06 plan/audit and exact acceptance source seam, then inspected the committed matrix and current temporary bundle. It found no additional source defect and made no edits. The existing acceptance boundary validates the canonical bundle hash and byte bound, pinned model revision/licence/dimension/snapshot, provider and tokenizer package/source/config/vocabulary hashes, provenance, and bridge-vocabulary linkage.

The review independently confirmed that closure remains evidence-bound: semantic replay is 22/32 hits with `0.3125` miss-rate against the ratified `0.10` threshold and `93/123` coverage (`0.7561`), with composed-ladder/all-locale parity still unproven and no accepted browser configuration. No threshold was lowered and no deployment was run.

### 2026-08-11 retirement under ADR Update 12

This row is retired, not delivered. There is no shipped matrix whose provenance stamp, model licence or size bound the gate could validate, so the extension has no subject.

What this retirement does not touch is equally important: every standing bar in the licence gate remains in force, on anything derived from NC, ND or gated sources, on raw oracle outputs, and on committing the heavy generated index. Under D14 the bounded-embedding exception is deliberately not re-narrowed either; it stays a documented, presently unused door with no consumer at HEAD, because a permission that oscillates is worse than one recorded as unused.

## Notes

- No tests, builds, model downloads, generated artifacts, Pagefind/runtime probes, live sweeps, RAG reindexing, or deployment were run.
- No source file was changed in this tranche; concurrent shared-worktree changes were preserved.
- Closure requires real manifest and provider evidence plus the authorized acceptance gates; the standing no-tests boundary remains in force.

### 2026-08-07 LUNA Extra High acceptance/provenance implementation

Fresh vaultspec-rag grounding and current bundle inspection preceded this bounded implementation. The acceptance boundary now binds the pinned provider/model/tokenizer identities to the exact current diagnostic evidence: model2vec 0.8.2, tokenizers 0.23.1, the immutable Potion revision, model-snapshot digest, provider-source digest, tokenizer vocabulary digest, and tokenizer configuration digest. It rejects mismatched model licence, provider/package/version/source, tokenizer/package/version/repository/revision/content roots, canonical bundle hash, and payload size before a browser configuration can validate.

The real-behaviour acceptance tests now cover canonical bundle hash and byte evidence, matrix self-attestation tampering, and each provider/tokenizer/model identity mismatch. The worker initially supplied stale provider/config values; a follow-up correction aligned them to the current locally validated bundle before proof. The post-correction acceptance slice returned 49 passed; the broader bounded Rung-2/search selection returned 98 passed. Ruff, basedpyright (0 errors, 0 warnings, 0 notes), Node syntax, and scoped diff checks passed.

This remains source and acceptance-boundary evidence only. The diagnostic bundle is not committed or enabled, the held-out/composed-ladder result remains below the ratified gate, and P02.S06 stays open.

### 2026-08-07 authoritative bundle provenance continuation

The current authoritative full-bundle compile now reaches the acceptance input boundary and round-trips through the production loader. The exact temporary bundle is schema v3, 2,138,574 canonical bytes, with bundle artifact SHA-256 `1cb0bb6761bfb54a5a768d202fef0b9b85d3a38de99b34f92297cf2204d47f12`, matrix artifact SHA-256 `d102c30db0a589854ac6ee4d0f1609d689a9dd5e5b23b61fe5063e3a1f6bbfda`, and the ratified Potion/model2vec/tokenizers provenance.

This clears the former input-projection failure but does not satisfy P02.S06: no browser acceptance evidence is supplied, semantic recall is 22/32 with 0.7560975609756098 aggregate coverage, the full ladder is not freshly hash-linked, and four-locale/per-kind parity for this bundle is unproven. The fail-closed browser configuration remains disabled; P02.S06 stays open.

Focused real-behaviour acceptance/evaluation/input/query-authority/report/sweep coverage returned `83 passed in 55.81s`, and the full bundle passed canonical load, matrix equality, and exact round-trip checks. This proves the source contracts and provenance shape, not release acceptance.

Fresh evaluation against that exact bundle under coverage floor `0.8`, cosine floor `0.75`, runner-up margin `0.05`, and result limit `5` returned 22/32 hits, 10 misses, miss rate `0.3125`, aggregate coverage `93/123 = 0.7560975609756098`, and all ten misses as `insufficient-coverage`. No cosine-floor or runner-up failure was observed. No approved browser configuration was emitted; the semantic tier remains fail-closed and P02.S06 remains open.
