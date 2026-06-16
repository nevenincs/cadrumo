---
name: glossary-concepts-are-taxpayer-facing
---

# Terminology Handbook glossary concepts are taxpayer-facing only

## Rule

Only a taxpayer- or operator-facing AEAT concept may be an `approved`
Terminology Handbook concept (and therefore render in the generated glossary and
the shipped Pagefind search injection): a tax, modelo, casilla, régimen, period,
legal concept, or an operator workflow noun (`ledger`, `borrador`,
`justificante`, `fichero-boe`). A concept that names the search / calculation /
registry MACHINERY (RAG sweep, relevance map, search projection, preprocessing
hook, search record kinds, licence laundering, preflight, registry binding, work
unit, verification-state internals, the Handbook itself) MUST NOT be `approved`;
it is `deprecated` (resolvable for the dev/agent RAG, excluded from the glossary
and shipped search) with a `scope_note` marking it internal, never deleted.

## Why

The corpus-quality drive (`2026-06-15-docs-terminology-search-audit`) found ~14
`approved` concepts documenting the search/calculation machinery itself, so the
glossary a taxpayer reads carried first-class entries for `barrido-rag`,
`proyeccion-busqueda`, `mapa-relevancia`, `work-unit`, and the like — none of
which a taxpayer would ever look up, none of which can carry a legal basis. The
decision is recorded in `2026-06-15-docs-terminology-search-adr` (D1/D2): the
Handbook's `approved` tier is the taxpayer/operator vocabulary; internal
concepts are demoted to `deprecated` (not `retired`, which asserts a successor
that a mis-enrolment lacks; not deleted, per the scaffold-preserve contract).
The glossary generator and the Pagefind injector both gate on `approved`, so the
lifecycle is the enforcement surface. The scaffold walks live enrolment sources,
so a future scaffold can re-surface an internal concept as a `draft` (harmless —
drafts are excluded); promoting one to `approved` is the regression this rule and
the curation audit guard against.

## How

- **Good:** `prorrata`, `modelo-303`, `recargo-equivalencia`, `casilla`,
  `borrador`, `ledger` are `approved` — taxpayer/operator terms — and render in
  the glossary.
- **Good:** `barrido-rag` (RAG sweep), `proyeccion-busqueda` (search
  projection), `binding` (registry binding), `work-unit` are `deprecated` with a
  `scope_note` recording they are internal machinery; the dev RAG still resolves
  them, the taxpayer glossary does not.
- **Bad:** promoting an internal/tooling concept to `lifecycle = "approved"`, so
  it renders as a first-class taxpayer glossary entry.
- **Bad:** deleting an internal concept fragment instead of deprecating it (the
  scaffold-preserve contract never deletes; deprecation keeps it resolvable for
  developers).

## Source

ADR `2026-06-15-docs-terminology-search-adr` (D1/D2); audit
`2026-06-15-docs-terminology-search-audit` (PERF-001 follow-up). Enforced by the
`approved`-only gate in the glossary generator (`dev/docs/glossary_reference.py`)
and the Pagefind injector (`dev/docs/pagefind_inject.py`). Companion rules:
`terminology-single-declaration`, `terminology-scaffold-preserve-contract`.
