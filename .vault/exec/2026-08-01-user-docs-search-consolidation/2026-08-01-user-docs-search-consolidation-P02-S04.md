---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:483a43cfb51a84907c6bdf5467de095e61dfa94ef2f4ac99db53573e2bd127d0'
step_id: 'S04'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
  - "[[2026-08-01-user-docs-search-consolidation-adr]]"
  - "[[2026-08-04-user-docs-search-consolidation-rung-2-static-embedding-boundary-research]]"
---

# Build the dev-side matrix compiler that embeds the closed vocabulary and its token inventory with the pinned model and emits the bounded int8 matrix as committed, reviewable, provenance-stamped data

## Scope

- `dev/docs/`

## Description

- Re-ground the compiler boundary with vaultspec-rag over the accepted ADR, P02.S03 research, the active plan, and the existing terminology sweep/miss-rate code.
- Add a model-agnostic dev-side compiler contract that canonicalises the closed vocabulary and records its SHA-256 fingerprint and deterministic row order.
- Require one finite, token-count-consistent provider observation per term, reject missing/duplicate/foreign rows, normalise vectors with float32 arithmetic, and emit symmetric per-row int8 values with explicit scales.
- Stamp the plain-data matrix with model repository, immutable revision, SPDX licence, dimension, token inventory, quantisation algorithm, serialized byte count, and artifact hash.
- Export the compiler surface through the terminology dev package and run source-only AST and whitespace checks.

## Outcome

The deterministic source seam for P02.S04 now exists in the dev tooling. It is deliberately model-agnostic: the provider must supply a pinned model metadata record and exact tokenised embeddings, while the compiler owns canonical vocabulary identity, coverage failures, quantisation, self-attestation, and the 3,000,000-byte hard ceiling. The browser and shipped product remain untouched.

P02.S04 is not closed. No model was selected or downloaded, no provider adapter or committed matrix was generated, and no client cosine tier or licence gate was added. Those remain measured follow-up work under P02.S04-P02.S07.

## Notes

The change was grounded by vaultspec-rag searches over the existing sweep, miss-rate evaluator, terminology package, accepted consolidation ADR, and Rung-2 research. The configured codebase alias rejection was not bypassed and no reindex was requested.

No tests, builds, model downloads, matrix generation, browser probes, live-service sweeps, deployment, or runtime gates were run. The formal source review is recorded separately and must pass before any future plan-state transition.

The formal remediation review recorded PASS for the four compiler strictness findings: required schema markers, exact canonical provider identity, float32 scale representation, and raw canonical artifact bytes. Vocabulary-source provenance and aggregate token-coverage evidence remain LOW follow-ons for P02.S05-P02.S07. The P02.S04 plan row remains open because this source seam has no ratified provider, generated matrix, or measured acceptance artifact yet.

### 2026-08-05 source continuation: strict typing boundary

RAG-grounded static validation found ten basedpyright findings where runtime fail-closed checks were unreachable under overly narrow annotations. Commit `68d1d2e59b` widens only the compiler and acceptance external boundaries to honest object/iterable inputs, narrows them explicitly after preserving every runtime guard, and aligns the compiler export order with Ruff.

Independent static verification passed: vaultspec-rag grounding, Ruff, basedpyright (`0 errors, 0 warnings, 0 notes`), Python AST parsing, JavaScript syntax checking, focused diff whitespace validation, and conflict-marker scanning. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run. P02.S04 remains open for the pinned provider/artifact and measured acceptance gates.

### 2026-08-05 source continuation: assembled-input identity guard

The authoritative `Rung2CompilationInputs` dataclass now revalidates canonical vocabulary/query-token order, recomputes both fingerprints, and requires the embedded provenance fingerprints to match before the provider-backed compiler can consume the assembled inputs. This strengthens the source-authority handoff without selecting a provider or generating an artifact. It does not close the remaining provider, model, matrix, or measured-acceptance gates for P02.S04.

Static evidence only: fresh vaultspec-rag grounding, AST parsing, and focused diff checks. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run.

### 2026-08-05 source continuation: authoritative assembled-input guard

Fresh vaultspec-rag grounding over the P02.S04 static-matrix audit, execution record, accepted ADR, and current input/compiler modules identified a remaining handoff weakness: the typed `Rung2CompilationInputs` dataclass revalidated fingerprints but did not fail closed when constructed with a non-authoritative runtime payload or when its sweep mappings disagreed with its stamped vocabulary/query-token identities. The source boundary now requires the exact validated `SweepResult`, `Rung2InputProvenance`, and tuple of authoritative `SearchRecord` values; rejects an empty or degraded sweep; and derives both canonical vocabulary surfaces from the committed sweep mappings before accepting the supplied fingerprints. This strengthens the existing project-authoritative handoff without changing provider, artifact, browser, or acceptance behavior. Static `basedpyright`, Ruff, and focused diff checks pass. No tests, builds, model downloads, matrix generation, runtime probes, live sweeps, reindexing, or deployment were run.

### 2026-08-05 fresh source disposition

Fresh vaultspec-rag searches over the P02.S04 plan/audit/reference and exact reads of `_rung2_inputs.py`, `_rung2_compiler.py`, `_static_matrix.py`, and `_model2vec_provider.py` confirm the current source boundary: the committed sweep and current Handbook derive the closed query vocabulary, the authoritative Pagefind projection supplies the record manifest, and provider/model/tokenizer evidence remains an explicit local input. No additional P02.S04 source defect is justified. The remaining blocker is the real pinned provider/package/model/tokenizer evidence, matrix generation, and measured acceptance artifact; no plan row is closed.

A Luna Max worker was dispatched for the same bounded input/compiler ownership but could not proceed because its required installed-version runtime-proof precondition was unavailable; it made no edit. No tests, builds, model downloads, matrix generation, runtime probes, live sweeps, reindexing, deployment, or artifact release were run.

### 2026-08-05 environment boundary confirmation

A fresh read-only environment check confirms that `model2vec` is not installed in the current `uv` environment (`find_spec` returned `None`), and the repository contains the provider/compiler source but no local model or matrix artifact. The project configuration deliberately omits a runtime `search` extra: semantic search is a dev-side precompile step and the shipped surface carries laundered output. The accepted provider contract therefore cannot be advanced by installing or downloading dependencies in this continuation; the pinned provider artifact, licence evidence, generated matrix, and measured acceptance gates remain open.

This check did not run tests, builds, model downloads, matrix generation, Pagefind compilation, browser probes, live sweeps, runtime gates, deployment, or generated-artifact release.

### 2026-08-05 current source re-audit

Fresh vaultspec-rag searches over the active plan, the accepted Rung-2 ADR updates, the source contract reference, and the current terminology modules found no new source-level defect in the P02.S04 boundary. The current audit records the schema-marker, canonical-observation, float32-scale, raw-artifact-canonicality, input-provenance, and R8 raw-manifest controls as source-remediated. The remaining requirements are real provider/package/model/tokenizer evidence, installed-version proof, matrix generation, licence/quantization/held-out acceptance, and runtime evidence; none is present or authorized in this continuation.

A requested Luna Max source delegation could not execute because the agent runtime required an unavailable Sol/custom-agent validation precondition; it made no edit. No tests, builds, model downloads, dependency installation, matrix or manifest generation, Pagefind/runtime probes, live sweeps, reindexing, deployment, or artifact release were run. P02.S04 remains open.

Fresh `vaultspec-rag` code searches and exact source reads covered the active L2 plan, accepted ADR Updates 6–10, the source contract reference, the P02.S04 audits, `_rung2_inputs.py`, `_rung2_compiler.py`, `_static_matrix.py`, `_model2vec_provider.py`, and `_content_manifest.py`.

The source boundary is complete for its authorized scope: the committed sweep and current Handbook derive canonical vocabulary/query-token identities; the authoritative Pagefind projection supplies records; the provider requires explicit local provider/model/tokenizer raw-byte manifests before import; the compiler composes the validated bundle and explicit writer; and the browser remains fail-closed without an accepted artifact. The RAG/source contract does not justify adding an unratified CLI or changing the existing entrypoint.

Static evidence for this continuation:

- Ruff passed for the scoped Rung-2 Python modules.
- `basedpyright` passed with 0 errors, 0 warnings, and 0 notes.
- Python AST parsing passed for the scoped Rung-2 modules.
- `node --check docs/_static/cadrumo-docs.js` passed.
- Scoped `git diff --check` passed and no conflict markers were found.

Open evidence tasklist (not a plan closure signal):

- OPEN — supply independently reviewed local provider-package, model-snapshot, tokenizer-vocabulary, and tokenizer-configuration manifest evidence.
- OPEN — prove the installed pinned provider/package and model revision/licence against those raw bytes without downloading.
- OPEN — compile the bounded matrix/bundle and record serialized-size, quantization-drift, and nested self-attestation evidence.
- OPEN — run the separately authorized P02.S05/P02.S06/P02.S07 behavioural, licence, and held-out acceptance gates.

No tests, builds, model downloads, matrix or manifest generation, Pagefind/runtime probes, live sweeps, reindexing, deployment, or generated-artifact release were run. P02.S04 remains open; the source implementation is not being represented as artifact or shipped-site acceptance.

## 2026-08-05 source continuation: browser-recognizable query-token contract

The source seam now distinguishes candidate result rows from the separate
query-token rows a future browser reader would average. The query-token rows
carry exact provider token text, model token ids, quantised values, and the
same dimension/scale/byte-bound checks as result rows. The matrix fingerprints
the query-token vocabulary separately, requires complete exact provider
coverage, and advances the schema marker to version 2. The terminology package
exports the new contract.

This continuation is intentionally model-agnostic and source-only. It does not
choose or download a model, implement the browser reader, generate a matrix,
or establish tokenizer/normalisation, cosine-threshold, drift, licence, or
held-out recall acceptance. Sol-medium architecture advice established that
P02.S05 cannot safely proceed while the matrix contains only term vectors and
token ids. P02.S04 remains open until the model and measured artifact gates
are satisfied; P02.S05 through P02.S07 remain open as planned.

The current source-only evidence is AST parsing and focused diff whitespace
validation. No tests, builds, model downloads, matrix generation, Pagefind
compilation, browser probes, live sweeps, runtime gates, or deployment were
run.

## 2026-08-05 source continuation: reject zero-valued quantized rows

The schema-v2 row validators now refuse an all-zero int8 result row and an
all-zero query-token row. This closes a source-level fail-open case in which a
positive scale and correctly sized byte vector could still carry no usable
semantic direction. Existing model-dimension, vocabulary-count, token-id,
hash, canonical-byte, and size checks remain unchanged.

This is still source-only hardening: no provider, model, matrix artifact,
browser reader, or measured acceptance gate was added. No tests, builds,
model downloads, matrix generation, Pagefind compilation, browser probes, live
sweeps, runtime gates, or deployment were run.

## 2026-08-05 deferred real-behaviour gates

The LUNA Extra-High worker added `test_static_matrix_contract.py` with direct
schema coverage for accepted non-zero result/query-token rows and rejected
all-zero rows. The tests use the production Pydantic models directly and do
not introduce test doubles or business logic. They were intentionally not run;
AST parsing and focused whitespace checks are the only verification for this
continuation.

## 2026-08-05 source continuation: ratified Rung-2 bridge and browser contract

The approved ADR Update 6 is now reflected in the source seam. The matrix contract carries schema-v3 provider/tokenizer provenance, the shared Unicode normalization contract, complete ordered model-token-id tuples and counts, and the existing float32/int8 and 3,000,000-byte guards. The new bridge projects the same authoritative SearchRecord identities used by Pagefind, links terms to ordered record_id/ranking-weight targets, and nests the matrix, bridge, and manifest in one bounded Rung2SearchBundle.

The shared browser controller now reads that bundle shape, validates the pinned model/licence/provenance/normalization markers, validates manifest and bridge hash links, performs the covered-token mean/L2/cosine seam, preserves exact structured casilla refusal and lexical-before-semantic precedence, deduplicates by record_id, and caps semantic candidates at five. Malformed or unavailable semantic data disables only the semantic tier and preserves Pagefind results.

The source-only formal review initially found four contract defects; the owned source was corrected for bundle-shape alignment, normalization/provenance alignment, Pagefind-preserving semantic failure, and direct-match precedence. The bridge target list is deterministically ordered and no longer imposes an unratified five-target source limit; the browser caps surfaced candidates at five.

Static verification only: Python AST parsing, JavaScript syntax checking, and focused diff whitespace validation passed. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, deployment, or generated-artifact release were run. P02.S04 remains open because the pinned provider artifact, licence acceptance, measured thresholds/drift/payload evidence, and runtime gates are still absent; P02.S05-P02.S07 remain open.

## 2026-08-05 post-fix review: alias precedence

The remaining medium review finding is closed by commit `96ba221c43`. The weight-sorted Pagefind card pass now marks injected records as lexical-card matches, covering declared alias hits even when the title differs; title matching remains the stronger intra-band signal, and semantic candidates remain additive and visible. The focused post-fix formal review returned PASS with no remaining findings.

Verification remains static-only: JavaScript syntax and focused diff whitespace checks passed. No tests, builds, model downloads, matrix/provider generation, Pagefind compilation, browser/runtime probes, live sweeps, deployment, or generated-artifact release were run.
