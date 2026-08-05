---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e0761f5702c04b616beeab2cf03b60f47b5a5bd6923c108d1cd908a34e21cc27'
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
