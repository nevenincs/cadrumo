---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3b879b6dad90fef29d7b0e3a7a19fbc9566a78ffc30b63e8ee7e90594e003297'
step_id: 'S21'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Carry registry help, input-kind, data-type, formula, and locale metadata through the casilla search projection and unified record without changing the opaque identity

## Scope

- `dev/docs/terminology/`

## Description

- Ground the projection against the registry's existing casilla detail contract.
- Carry localized help, data type, input kind, requiredness, binding, and formula identity through the casilla projection and unified metadata.
- Render the definition fields and locale fallback on the generated casilla reference surface without changing the opaque identity.

## Outcome

Commit `77c2e8ea49` carries registry-backed definition metadata through the casilla search record and destination surface. Formula expressions are intentionally not invented: the projection carries the canonical formula id, while the authoritative formula table remains outside this projection seam.

## Tracking

- Opaque `(modelo, casilla_id)` identity unchanged: complete.
- Localized labels and help with Spanish fallback: complete.
- Input kind, data type, requiredness, binding, and formula id: complete.
- Formula expression parity with the registry detail query: pending a later detail/build gate.
- Built Pagefind metadata/browser rendering: pending P06.S24/P04.S11; not run in this step.

## Notes

The implementation agent ran RAG discovery, owned-file history/diff checks, and `git diff --check`. Tests, builds, Pagefind compilation, deployment, and live probes were not run. The mandatory code-review pass is still pending; the step must not be marked closed until that review returns.
