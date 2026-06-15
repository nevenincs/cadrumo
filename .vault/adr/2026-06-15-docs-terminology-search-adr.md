---
tags:
  - '#adr'
  - '#docs-terminology-search'
date: '2026-06-15'
modified: '2026-06-15'
related:
  - '[[2026-06-10-docs-terminology-search-research]]'
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-15-docs-terminology-search-audit]]'
---

# `docs-terminology-search` adr: `glossary enrolment policy and committed-artifact boundary` | (**status:** `accepted`)

## Problem Statement

The corpus-quality drive (audit `2026-06-15-docs-terminology-search`) surfaced
two questions the original architecture ADR
(`2026-06-10-docs-terminology-search-adr`) did not settle, and which a fresh
agent cannot resolve from the code alone:

1. **What may be an APPROVED, taxpayer-facing glossary concept?** The Handbook
   accumulated ~14 APPROVED concepts that document the search/calculation
   MACHINERY itself — `barrido-rag` (the RAG sweep), `proyeccion-busqueda`
   (search projection), `mapa-relevancia` (the relevance map),
   `gancho-preprocesado` (preprocessing hook), `clases-registro-busqueda`
   (search record kinds), `depuracion-licencia` (licence laundering),
   `manual-terminologia` (the Handbook itself), `preflight`, `binding`,
   `work-unit`, `verificado-completo`. These render as first-class entries in a
   glossary a taxpayer reads, and none has (or can have) a legal basis. They are
   noise in the user-facing surface.

2. **What ships committed vs regenerated?** A 63 MB / ~16k-file compiled
   Pagefind index had been committed to git at the repo root, contradicting the
   uncommitted-index intent of the original D5. The boundary between the
   committed precompiled DATA and the uncommitted generated INDEX needs to be
   stated as policy, not folklore.

## Considerations

- The original ADR's purpose statement frames the Handbook as the
  reader-facing terminology surface ("what does pro rata mean") grounded in
  AEAT/BOE sources. Internal engineering concepts are outside that purpose.
- The Handbook is also indexed by the dev/agent `vaultspec-rag` service, where
  the internal concepts ARE useful (a developer searching "relevance map" wants
  them). So the decision is about the SHIPPED, approved, taxpayer surface — not
  about deleting the concepts.
- The lifecycle model already distinguishes `APPROVED` (curated, shippable,
  glossary-rendered) from `DEPRECATED` (resolvable but not glossary-rendered)
  and `RETIRED` (tombstoned, requires a successor). The glossary generator and
  the Pagefind injector both gate on `APPROVED`.
- `RETIRED` requires `replaced_by`; a mis-enrolled internal concept has no
  taxpayer successor, so retirement is the wrong tool. `DEPRECATED` fits: it
  removes the concept from the approved-only glossary and the shipped search
  injection while keeping it resolvable for the dev RAG and never deleting it.
- The committed precompiled artefacts (the Handbook fragments, the laundered
  `relevance.json`, the synonym-candidate and held-out-query data) are small,
  reviewable, plain data CI cannot regenerate. The Pagefind index
  (`pagefind/` — fragments, index shards, wasm; thousands of files, tens of MB)
  is a deterministic build output regenerated every docs build.

## Decision

**D1 — The APPROVED/glossary tier is taxpayer- and operator-facing only.** A
concept is eligible for `lifecycle = "approved"` (and therefore for the
generated glossary and the shipped Pagefind injection) ONLY if it names a term
a taxpayer or operator meets on an AEAT surface, in the docs, or at the CLI: a
tax, modelo, casilla, régimen, period, legal concept, or an operator workflow
noun (e.g. `ledger`, `borrador`, `justificante`, `fichero-boe`). A concept that
names the search/calculation/registry MACHINERY (RAG sweep, relevance map,
search projection, preprocessing hook, record kinds, licence laundering,
preflight, registry binding, work unit, verification-state internals, the
Handbook itself) MUST NOT be APPROVED.

**D2 — Mis-enrolled internal concepts are DEPRECATED, not retired or deleted.**
The internal concepts above are set to `lifecycle = "deprecated"` with a
`scope_note` recording that they document internal machinery and are excluded
from the taxpayer surface. They stay resolvable for the dev/agent RAG and are
never deleted (the scaffold-preserve contract). Retirement is reserved for a
concept genuinely superseded by a named successor.

**D3 — Committed light data, uncommitted heavy index.** The committed,
reviewable, CI-consumed artefacts are the Handbook TOML fragments and the
laundered precompiled data under `src/aeat/_data/terminology/` (the
`relevance.json` term-to-target mapping, synonym candidates, held-out queries).
The compiled Pagefind index (`pagefind/`, the per-language fragment/index/wasm
corpus — thousands of files) is a generated build output: it is gitignored,
regenerated on every docs build, and MUST NOT be committed. A light, reviewable
precompiled DATA file may be committed; the heavy generated INDEX corpus may
not.

## Rationale

- **Why a policy, not a one-off cleanup:** the scaffold walks live enrolment
  sources, so an internal concept can be re-enrolled; the policy (and the audit
  gate it implies) is what keeps the taxpayer glossary clean across future
  scaffolds.
- **Why DEPRECATED over RETIRED:** retirement asserts a successor that does not
  exist for a mis-enrolment; deprecation states the truth — the concept is real
  but not taxpayer-facing — and is reversible if a concept later earns a
  taxpayer definition.
- **Why the artefact boundary is explicit:** the 63 MB committed index was the
  concrete failure; stating "light data committed, heavy index generated"
  prevents the next agent from re-committing a build output, and it matches the
  D5 intent that CI and readers consume laundered data, never the raw index.

## Consequences

- The glossary and shipped search drop ~14 noise entries; the taxpayer surface
  is the tax vocabulary only. The dev RAG still resolves the internal concepts.
- A future scaffold that re-enrols an internal concept as a draft is fine
  (drafts are excluded already); promoting one to APPROVED is the regression the
  policy and a curation-audit check guard against.
- `pagefind/` is gitignored at the repo root (done); the committed surface is
  the light `relevance.json` plus the Handbook fragments.

## Codification candidates

- **Rule slug:** `glossary-concepts-are-taxpayer-facing`. **Rule:** Only
  taxpayer/operator-facing AEAT concepts may be APPROVED Terminology Handbook
  concepts; internal search/calculation/registry machinery concepts must be
  DEPRECATED (resolvable for the dev RAG, excluded from the glossary and shipped
  search), never APPROVED.
- **Rule slug:** `shipped-search-light-data-not-heavy-index` (or fold into the
  existing `shipped-search-licence-clean`). **Rule:** Commit the light
  precompiled terminology data (`relevance.json`, synonym candidates, held-out
  queries, Handbook fragments); never commit the generated Pagefind index
  corpus (`pagefind/`), which is gitignored and regenerated every build.
