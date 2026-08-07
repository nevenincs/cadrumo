---
name: glossary-concepts-are-taxpayer-facing
trigger: always_on
---

# Terminology Handbook glossary concepts are taxpayer-facing only

Only a taxpayer- or operator-facing AEAT concept may be an `approved` Terminology
Handbook concept, and thus render in the generated glossary and the shipped
search index: a tax, modelo, casilla, régimen, period, legal concept, or operator
workflow noun (`ledger`, `borrador`, `justificante`, `fichero-boe`).

A concept naming the search, calculation or registry **machinery** — RAG sweep,
relevance map, search projection, preprocessing hook, licence laundering,
preflight, registry binding, work unit, verification-state internals, the
Handbook itself — MUST NOT be `approved`. It is `deprecated`: resolvable for the
developer and agent RAG, excluded from the glossary and shipped search, with a
`scope_note` marking it internal. **Never deleted.**

Roughly fourteen `approved` concepts once documented the machinery itself — none
a taxpayer would look up, none carrying a legal basis. `deprecated` is the right
state rather than `retired` (which asserts a successor a mis-enrolment lacks) or
deletion (which the scaffold-preserve contract forbids). The glossary generator
and the search injector both gate on `approved`, and a scaffold re-surfaces an
internal concept only as an excluded `draft`, so promoting one to `approved` is
the guarded regression.

## How

- **Good:** `prorrata`, `modelo-303`, `recargo-equivalencia`, `casilla`,
  `borrador`, `ledger` are `approved` and render; the machinery concepts are
  `deprecated` with a `scope_note` — the dev RAG resolves them, the taxpayer
  glossary does not.
- **Bad:** promoting an internal or tooling concept to `approved`; or deleting an
  internal concept fragment instead of deprecating it.

Source: ADR `2026-06-15-docs-terminology-search-adr` (D1, D2). Enforced by the
`approved`-only gate in the glossary generator and the search injector.
Companion: `terminology-single-declaration`.
