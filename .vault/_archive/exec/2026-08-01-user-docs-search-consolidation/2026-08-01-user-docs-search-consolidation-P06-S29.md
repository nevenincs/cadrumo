---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:5db75d8a69521ef58218b705665804e3dd6d59141859ca410a9b5b7705e3147c'
step_id: 'S29'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Correct the structured modelo plus casilla route to carry and match canonical casilla_id while retaining display-number and segmento fallback, and add the real-authority gate for an id that differs from its display number

## Scope

- `dev/docs/pagefind_inject.py`
- `docs/_static/cadrumo-docs.js`
- `dev/docs/terminology/tests/test_casilla_projection.py`

## Description

- Ground the canonical identity contract and the production projection/unified-record seams with vaultspec-rag before editing.
- Confirm from the bundled authority that Modelo 121 declares canonical id `decl.ejercicio` with display number `ejercicio`.
- Add a real-authority regression gate that checks the authoritative row, production projection, and unified typed metadata preserve the distinct identity and display fields.
- Add Pagefind `casilla_id` metadata and make the structured browser route compare the complete canonical token before retaining number/segment fallback.
- Review the gate and source correction with a LUNA Extra High code-review agent.
- Stage and commit only the canonical additions while preserving all unrelated peer WIP in the two affected files.

## Outcome

The real-authority regression gate is present in `dev/docs/terminology/tests/test_casilla_projection.py`. Commit `3127a58c7b` adds canonical `casilla_id` Pagefind metadata, preserves the complete structured query token, performs canonical matching first, and retains display-number/segment fallback. P06.S29 remains open because the required gates and built/runtime evidence are not authorized or available yet; P06.S24 remains open for the broader acceptance gate.

## Verification

No tests, typing gates, builds, generated artifacts, browser probes, sweeps, reindexing, deployment, or release actions were run. The scoped `git diff --check` completed with exit code 0 before commit. LUNA Extra High review reported no findings. VaultSpec check reported zero errors and one pre-existing stale feature-index warning. The RAG code route reported the current target-matching index and canonical identity sources.

## Notes

The source test gate and canonical matcher are intentionally unexecuted/unprobed under the explicit no-tests boundary. The shared worktree retains unrelated peer WIP in the same two files; those changes were preserved and not broadly staged, committed, or overwritten.

### 2026-08-06 authorized execution

The canonical identity gate is now included in the green 63-test marker-aware run. The full English Pagefind build and independent structured capture also exercised the shipped metadata path: M130/casilla 15 resolved to `casilla-record:63300419eb4c0e5119307cfc` and `_generated/casillas/130.html#casilla-15`. The canonical id remains separate from display number where the registry requires it; no fallback or synthetic record was used. Other locale source fields remain parity-checked, while strict locale artifact builds remain blocked by the recorded sequence/product divergences.
