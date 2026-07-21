---
name: glossary-concepts-are-taxpayer-facing
trigger: always_on
---

# Terminology Handbook glossary concepts are taxpayer-facing only

## Rule

Only a taxpayer- or operator-facing AEAT concept may be an `approved` Terminology
Handbook concept (and thus render in the generated glossary and shipped Pagefind
search): a tax, modelo, casilla, régimen, period, legal concept, or operator workflow
noun (`ledger`, `borrador`, `justificante`, `fichero-boe`). A concept naming the
search/calculation/registry MACHINERY (RAG sweep, relevance map, search projection,
preprocessing hook, search record kinds, licence laundering, preflight, registry
binding, work unit, verification-state internals, the Handbook itself) MUST NOT be
`approved`; it is `deprecated` (resolvable for the dev/agent RAG, excluded from the
glossary and shipped search) with a `scope_note` marking it internal, never deleted.

## Why

The corpus-quality drive (`2026-06-15-docs-terminology-search-audit`) found ~14
`approved` concepts documenting the machinery itself (`barrido-rag`,
`proyeccion-busqueda`, `work-unit`, …) — none a taxpayer would look up or that carries
a legal basis. `2026-06-15-docs-terminology-search-adr` (D1/D2) demotes them to
`deprecated` (not `retired`, which asserts a successor a mis-enrolment lacks; not
deleted, per the scaffold-preserve contract); the glossary generator and Pagefind
injector both gate on `approved`, and a scaffold re-surfaces an internal concept only
as an excluded `draft`, so promoting one to `approved` is the guarded regression.

## How

- **Good:** `prorrata`, `modelo-303`, `recargo-equivalencia`, `casilla`, `borrador`,
  `ledger` are `approved` and render; `barrido-rag`, `proyeccion-busqueda`, `binding`,
  `work-unit` are `deprecated` with a `scope_note` — the dev RAG resolves them, the
  taxpayer glossary does not.
- **Bad:** promoting an internal/tooling concept to `lifecycle = "approved"`; or
  deleting an internal concept fragment instead of deprecating it (the scaffold-preserve
  contract never deletes; deprecation keeps it dev-resolvable).

## Source

ADR `2026-06-15-docs-terminology-search-adr` (D1/D2); audit
`2026-06-15-docs-terminology-search-audit` (PERF-001). Enforced by the `approved`-only
gate in `dev/docs/glossary_reference.py` and `dev/docs/pagefind_inject.py`. Companion:
`terminology-single-declaration`, `terminology-scaffold-preserve-contract`.
