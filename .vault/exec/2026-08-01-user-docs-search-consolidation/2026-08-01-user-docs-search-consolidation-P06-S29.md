---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:07094350912f01464cebd813dcdcdbedbdfe33f7c12e012643499dde49d24556'
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
- Review the gate with a LUNA Extra High code-review agent.
- Leave the peer-owned Pagefind injector and shared browser controller unchanged until their unrelated WIP is released or coordinated for integration.

## Outcome

The real-authority regression gate is present in `dev/docs/terminology/tests/test_casilla_projection.py`. It proves that projection and unified metadata do not collapse canonical `casilla_id` into display `number`. The Pagefind metadata/matcher correction remains open and is tracked by P06.S29; P06.S24 remains open for the broader acceptance gate.

## Verification

No tests, typing gates, builds, generated artifacts, browser probes, sweeps, reindexing, deployment, or release actions were run. The scoped `git diff --check` completed with exit code 0. LUNA Extra High review reported no findings. VaultSpec check reported zero errors and one pre-existing stale feature-index warning.

## Notes

The source test gate is intentionally unexecuted under the explicit no-tests boundary. The shared worktree contains unrelated peer WIP, including changes in `dev/docs/pagefind_inject.py` and `docs/_static/cadrumo-docs.js`; those changes were preserved and not broadly staged or overwritten.
