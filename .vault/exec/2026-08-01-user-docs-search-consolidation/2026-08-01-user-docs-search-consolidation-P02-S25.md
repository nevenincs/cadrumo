---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:fc79febfa5155cb1fc399f3fd234f0df318179ff03792712a4d527879161a7e3'
step_id: 'S25'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Establish a shared canonical JSON byte contract or equivalent artifact evidence so the browser can fail closed on nested matrix, manifest, bridge, target-list, and bundle self-attestation hashes before Rung-2 artifact acceptance

## Scope

- `dev/docs/terminology/ and docs/_static/cadrumo-docs.js`

## Description

- [x] Ground the P02.S25 seam with fresh `vaultspec-rag` searches over the canonicalizer, bridge schemas, browser validation, and nested attestation code.
- [x] Obtain SOL approval for the cross-runtime canonical JSON contract and record the amendment in the governing ADR.
- [x] Dispatch the validated LUNA Max coding worker for source-only implementation of the shared canonicalization and nested self-attestation seam.
- [x] Run the configured formal source review before treating the step as complete.
- [ ] Produce independently checked Python/JavaScript golden-vector parity evidence.
- [ ] Complete P02.S25 only after the parity evidence and the remaining verification gates are authorized.

## Outcome

The source seam now carries the agreed `cadrumo-jcs-utf8-lf-v1` contract, versioned matrix/manifest/bridge/bundle schemas, input provenance, nested canonical-byte validation, and fail-closed self-attestation scaffolding. SOL approved the ADR amendment before implementation. The LUNA Max worker made the scoped source changes without running tests, builds, runtime probes, artifact generation, live sweeps, reindexing, or deployment.

The formal configured SOL review failed closure because the Python and browser number serialization paths have not been independently proven equivalent with golden vectors. The review also identified that the new Python canonicalizer remains untracked in the shared worktree; it must be included only through deliberate path-scoped handling.

## Notes

P02.S25 remains open. The current Python number spelling uses Python `repr(float)` plus normalization and therefore needs independent parity evidence against the browser implementation before it can be accepted as the contract. Shared-worktree peer changes were preserved and no broad staging or cleanup was performed.

A second validated LUNA Max pass re-grounded the Python and browser implementations and made no edit: exact ECMAScript shortest-round-trip and tie-breaking parity cannot be claimed without the independently checked vectors that the current no-verification boundary prohibits. No tests, builds, runtime probes, golden vectors, artifacts, sweeps, reindexing, or deployment were run.

### 2026-08-05 source continuation: manifest canonicalizer alignment

Fresh vaultspec-rag grounding over the accepted cross-runtime canonical JSON amendment and the raw-byte manifest implementation identified one remaining duplicate serializer: the raw-byte manifest root and envelope used a local compact `json.dumps` path instead of the shared `cadrumo-jcs-utf8-lf-v1` contract. `_content_manifest.py` now delegates manifest canonical bytes and root hashing to the shared canonicalizer, preserving the existing error boundary and preventing Python-only hash semantics from entering P02.S26 evidence.

Static evidence only: post-edit vaultspec-rag search, Python AST parsing, and focused diff whitespace validation passed. The independent Python/JavaScript golden-vector parity gate remains open. No tests, builds, model downloads, manifest or matrix generation, runtime probes, sweeps, reindexing, deployment, or artifact release were run.

### 2026-08-05 source continuation: committed JCS vector corpus

Fresh vaultspec-rag grounding of ADR Update 10 and the current Python/browser canonicalizers preceded a bounded source-only addition under `dev/docs/terminology/jcs_vectors/`. The new language-neutral corpus records admissible numeric, safe-integer, control-escape, multilingual/non-BMP, composed/decomposed, surrogate-rejection, nested-value, terminal-LF, and representative matrix/manifest/bridge/bundle hash-scope vectors. It includes a Python consumer that imports `canonical_json_bytes` directly and an independent JavaScript consumer; neither consumer was executed.

Static-only evidence for the new files: JSON parsing, Ruff, basedpyright, `node --check`, and `git diff --check` passed. No tests, builds, model downloads, matrix generation, generated artifacts, browser/runtime probes, live sweeps, reindexing, deployment, or release acceptance were run. P02.S25 remains open pending authorized execution of the independent parity evidence and the broader Rung-2 gates.

### 2026-08-05 vector-contract correction

Exact source inspection found that the Python and independent JavaScript consumers both reject integer-valued binary64 numbers outside the safe-integer domain. The `scientific-at-upper-threshold` corpus vector is therefore a deliberate rejection vector rather than an accepted byte vector, keeping the language-neutral corpus aligned with both production consumers. JSON parsing, `node --check`, and focused diff checks pass; neither consumer was executed. P02.S25 remains open for authorized independent parity evidence.

### 2026-08-05 cross-runtime source re-audit

Fresh vaultspec-rag code searches for Python artifact-hash projections, browser `rung2AttestBundle`, and the shared JCS canonicalizer, paired with vault searches over ADR Update 10 and the source-contract audit, were followed by full reads of `_rung2_bridge.py`, `_static_matrix.py`, `_content_manifest.py`, `_jcs.py`, and `docs/_static/cadrumo-docs.js`, plus exact symbol confirmation. The source structure matches the accepted hash scopes: matrix excludes its hash and size; record manifests hash the ordered records array; bridge target lists hash their ordered targets; bridge and bundle artifacts exclude their own hash and size; and the browser independently recomputes those nested scopes and the complete canonical bundle bytes before acceptance.

The Python and browser source surfaces also implement the ratified strict UTF-8, UTF-16-key-order, safe-number, surrogate, and terminal-LF contract. This is source alignment only, not cross-runtime proof: the independent Python/JavaScript vector consumers remain unexecuted under the current no-tests/no-verification boundary. No source correction is justified in this slice, and P02.S25 remains open for authorized parity evidence and the downstream Rung-2 gates. No tests, builds, model downloads, matrix or manifest generation, runtime probes, live sweeps, reindexing, deployment, or artifact release were run.

### 2026-08-05 current browser hash-attestation re-audit

A fresh vaultspec-rag code search for the browser nested self-attestation seam, followed by exact source inspection, confirms that the current implementation already contains `rung2ValidateMatrix`, `rung2ValidateManifest`, `rung2ValidateBridge`, `rung2ValidateBundle`, and `rung2AttestBundle`. The browser recomputes the accepted nested scopes for matrix bytes, manifest record bytes, bridge target-list bytes, bridge bytes, and bundle bytes, then checks the outer payload hash and vocabulary/query-token fingerprints before enabling the semantic tier; failures return a disabled result.

This current source fact supersedes the earlier review's statement that browser nested hash parity was still absent. That historical statement is retained above for audit continuity; no source duplication or correction is justified in this slice.

The remaining P02.S25 evidence gap is independent execution of the Python and JavaScript golden-vector consumers. The committed vector corpus is present in shared peer WIP, but neither consumer was executed under the standing no-tests/no-verification boundary. P02.S25 therefore remains open pending authorized parity execution and the downstream artifact/runtime acceptance gates. No tests, builds, model downloads, matrix or manifest generation, runtime probes, sweeps, reindexing, deployment, or release acceptance were run.
