---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:a60084759290ae19debec27c96bd6ba30f2aa9e410dc36a6a6c8d62a6ac899b8'
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

Commits `77c2e8ea49` and `ea5e441d7c` carry registry-backed definition metadata through the casilla search record and destination surface, with whitespace-only localized values treated as absent before Spanish fallback. Formula expressions are intentionally not invented: the projection carries the canonical formula id, while the authoritative formula table remains outside this projection seam.

## Tracking

- Opaque `(modelo, casilla_id)` identity unchanged: complete.
- Localized labels and help with Spanish fallback: complete.
- Whitespace-only localized labels/help treated as absent before fallback: complete.
- Input kind, data type, requiredness, binding, and formula id: complete.
- Formula expression parity with the registry detail query: pending a later detail/build gate.
- Built Pagefind metadata/browser rendering: pending P06.S24/P04.S11; not run in this step.

## Notes

The implementation agent ran RAG discovery, owned-file history/diff checks, and `git diff --check`. The focused formal reviewer inspected the full file and exact `ea5e441d7c` diff and returned PASS with no findings, including the whitespace normalization, Spanish fallback, and RST escaping boundary. Tests, builds, Pagefind compilation, deployment, and live probes were not run. P06.S24 still owns the runtime locale/detail and built-surface gates.
