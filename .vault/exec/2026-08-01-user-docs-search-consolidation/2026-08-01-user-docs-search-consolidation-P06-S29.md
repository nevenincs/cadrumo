---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:15e41e9fee4f1ca68933e242fc4a52226d4d8db14496a479c511225ecf58b8b1'
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
- Preserve all unrelated peer WIP in the two affected files; do not broadly stage or commit them.

## Outcome

The real-authority regression gate is present in `dev/docs/terminology/tests/test_casilla_projection.py`. The source correction is present in the uncommitted peer-owned hunks of `dev/docs/pagefind_inject.py` and `docs/_static/cadrumo-docs.js`: canonical `casilla_id` is emitted, the full query token is preserved, canonical matching is attempted first, and display-number/segment fallback remains. P06.S29 remains open because the required gates and built/runtime evidence are not authorized or available yet; P06.S24 remains open for the broader acceptance gate.

## Verification

No tests, typing gates, builds, generated artifacts, browser probes, sweeps, reindexing, deployment, or release actions were run. The scoped `git diff --check` completed with exit code 0. LUNA Extra High review reported no findings. VaultSpec check reported zero errors and one pre-existing stale feature-index warning. The RAG code route reported the current target-matching index and canonical identity sources.

## Notes

The source test gate and canonical matcher are intentionally unexecuted/unprobed under the explicit no-tests boundary. The shared worktree contains unrelated peer WIP in the same two files; those changes were preserved and not broadly staged, committed, or overwritten.
