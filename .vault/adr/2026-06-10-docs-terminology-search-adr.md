---
tags:
  - '#adr'
  - '#docs-terminology-search'
date: '2026-06-10'
related:
  - "[[2026-06-10-docs-terminology-search-research]]"
---

# `docs-terminology-search` adr: `terminology handbook and precompiled docs search` | (**status:** `accepted`)

## Problem Statement

The shipped documentation has no meaningful terminology surface: search is
the stock English-stemmed Sphinx index plus a nav-titles-only command
palette, while the vocabulary the reader actually needs (modelo, casilla,
IVA categories, prorrata, justificante, legal provisions, CLI verbs) is
hand-redeclared across at least four unsynchronised stores with zero
conformance gating — a direct violation of the docs-architecture
codebase-state-as-truth principle, which is enforced for commands but not
for terminology. The dev-side vaultspec-rag vector database cannot ship
(CUDA hard-refusal, SPLADE CC BY-NC-SA licence taint, 1.9 GB pickled
exclusive-locked store), so the shipped docs need their own precompiled
search backend.

The reader's need is dual. They navigate the CLI and codebase surfaces
(commands, options, worked examples) AND they look up what text terms mean.
A query for "pro rata" must return meaningful, linked results: the concept's
definition, the legal grounding resources the code itself is grounded
against (BOE provisions, corpus normative anchors), and the modelo casilla
schema descriptions — every casilla carries a localised description
conforming to the official casilla descriptions. One search must serve all
three result kinds.

This ADR decides the architecture. Operator pre-decisions bind it: the
compiled search database is NOT committed (mirroring the uncommitted HTML
build output); the enrolled terminology IS committed as a continuously
improved artefact; and the middle layer between registry compilation and
shipped documentation is a programmatically generated **Terminology
Handbook**. A further operator directive grounds the technical centre of
gravity: the information already exists — casilla and modelo definitions,
crosslinked references, legal grounding — and the question is how to
compile it against natural-language search, prebuilding what a RAG does on
the fly; heavy build-time RAG utilisation, and the RAG index's capability,
transformation, preprocessing, and output wrangling, are first-class
concerns of this decision.

## Considerations

- **Three result kinds, one query.** Concept cards (definition + legal
  grounding), casilla records (localised descriptions + legal_refs), and
  CLI/docs surfaces (verbs, how-tos, API reference) must rank together.
  The backend is therefore a unified index over heterogeneous typed
  records, not a glossary page with search bolted on.
- **Authoritative sources already exist, typed and shipped.** Registry
  snapshots (18,885 casillas with Spanish labels, legal_refs, source_refs;
  per-revision locale fragments for en/ca/hu where authored), the legal
  catalogue (262 provisions with BOE permalinks and corpus anchors), core
  enums (Modelo, IvaCategory, periods), 13 registry topics, the
  introspectable Typer tree, and the quad-lingual locale catalogue
  (2,855 keys x 4). The Handbook must consume these through
  `ValidatedRegistryAuthority` snapshots and enum imports, never re-parse
  fragments (registry-authority-flow rule).
- **Generated-then-curated tension.** The Handbook is programmatically
  scaffolded from those sources AND hand-curated (definitions, scope
  notes, aliases). Regeneration must never clobber curation. The canonical
  prior art is GNU gettext `msgmerge`: preserve / scaffold-empty /
  retire-as-tombstone. The house precedents are `aeat.locales scaffold`
  and `dev.docs.apidocs scaffold --check`.
- **Search engine candidates** (full survey in the research document):
  Pagefind (MIT; native es/ca/hu stemming with per-language index splits;
  chunked lazy index ~100-300 KB read-time at 10k+ pages; Python/Node
  `addCustomRecord` API for injecting precompiled term records as
  first-class weighted entries; proven Sphinx+Furo prior art) versus Orama
  (Apache-2.0 pure-JS; prebuilt-index persistence; no Catalan stemmer
  bundled; whole-index load). Rejected: Stork (unmaintained), tinysearch,
  Fuse.js, FlexSearch (no es/ca stemming, no synonyms), Sphinx native
  search (single-stemmer architecture), every hosted service (network at
  read time).
- **Semantics ladder** (research P2): rung 1 ships embedding-mined,
  human-ratified synonym rings as plain JSON; rung 2 ships a static int8
  term-embedding matrix (~1-3 MB) with client-side cosine; rung 3 ships a
  ~30 MB browser transformer. Term records already carry four declared
  translations, so cross-lingual matching is free at rung 1; rung 3's only
  unique capability (live embedding of uncatalogued free text) does not
  justify its footprint.
- **Schema standards**: TBX/ISO 30042 concept-oriented three-tier model
  (concept → language section → term section) and SKOS label/relation
  vocabulary are the mature data models; both map naturally onto the
  registry's TOML-fragments-compiled-to-strict-pydantic house pattern.
- **External seeds**: IATE TBX bulk download (es/hu/en; permissive with
  attribution, download-file only), UBTERM Diccionari de fiscalitat
  (ca/es/en, CC BY 3.0), EuroVoc SKOS labels (licence to verify) are
  ingestible; AEAT Manuales Prácticos, INFORMA, DG TAXUD, and BOE are
  authoritative link-only grounding. TERMCAT Terminologia Oberta
  (CC BY-ND) and RAE DPEJ (no download) are excluded from ingestion.

## Constraints

- **Offline-hermetic docs build, no GPU in CI.** The deterministic pipeline
  (enrol → compile → gate) must run on CPU with no network. Anything
  embedding-derived runs only on the GPU dev box and lands as committed,
  reviewable plain data; CI consumes it, never regenerates it.
- **Licence-clean shipping.** Nothing CC BY-NC / CC BY-ND / gated may ship
  or be derived into shipped artefacts. SPLADE-derived data is forbidden in
  any shipped form. Pagefind is MIT; potion/Model2Vec is MIT; Qwen3
  embeddings are Apache-2.0 (model outputs shippable).
- **Pagefind binary vendoring.** Pagefind ships as a downloaded
  binary/wheel; the offline-hermetic gate requires vendoring it as a pinned
  dev dependency. If vendoring proves untenable, the fallback is Orama plus
  a sourced Catalan Snowball stemmer and acceptance of whole-index loading.
- **Casilla translation sparseness.** Registry per-revision locale
  fragments exist for only a handful of modelos today; casilla search
  records are mostly Spanish-labelled until the registry locale surface
  grows. That growth is registry work, outside this feature's scope; the
  compiler consumes whatever exists.
- **Scale ceiling.** 18,885 casillas must not become 18,885 hand-curated
  handbook entries or 18,885 glossary page rows; the architecture must
  split hand-curated concepts from machine-projected records.
- **Parent-feature stability.** The registry authority/snapshot pipeline,
  the locales CLI discipline, the apidocs scaffolder, the docs conformance
  gates, and the Ctrl-K palette are all landed and stable; this feature
  composes them and introduces no new runtime service. The single
  genuinely novel, unproven element is the redeclaration prose gate (no
  surveyed system has one); it is built as a docs-marked AST/regex
  conformance test and can land incrementally.

## Implementation

Three layers, strictly separated by commit status:

`enrolment sources (committed, already exist) -> Terminology Handbook
(committed, scaffolded + curated) -> compiled search + glossary artefacts
(NOT committed, regenerated every docs build)`.

**D1 — The Terminology Handbook is a TOML authoring tree** under
`src/aeat/_data/terminology/`, one fragment per concept, shipped in the
wheel like its registry sibling, compiled by a strict loader into typed
pydantic records (the registry authoring-compiler house pattern). The
authoring surface is data, reviewable in diffs, continuously improved —
the operator-mandated middle layer.

**D2 — Concept-oriented schema** (TBX/SKOS-informed, decided subset).
Concept level: `concept_id` (Spanish stem, immutable, never reused),
`domain` (closed StrEnum: `concepto | modelo | casilla-namespace | regimen
| periodo | cli-verb | legal`), `domain_refs` (typed ids into registry
entities), `legal_refs` (must resolve in the legal catalogue, which
resolves to BOE permalinks and corpus anchors), `broader` / `related`
(shallow SKOS relations; `narrower` derived at load), `lifecycle` (`draft |
approved | deprecated | retired`), `replaced_by` (mandatory when retired —
tombstones, never deletion), `seed_provenance` (which external source
seeded the entry, with attribution string), dates. Language sections
(es/en/ca/hu): `definition` (es grounded against AEAT/BOE sources via
`source` citation), `scope_note`, required `short_description` (the
tooltip/card text — first-class, never inferred from prose). Term
sections: `label`, `term_status` (`preferred | admitted | deprecated |
forbidden`), `hidden_search_forms` (unaccented/misspelt variants),
grammatical fields where relevant. Per-term-status modelling carries the
synonym surface declaratively: "pro rata" and "prorrateo" are admitted
terms on the `prorrata` concept.

**D3 — Scaffold lifecycle with the msgmerge three-outcome contract**,
operated by a `python -m aeat.terminology` CLI mirroring `aeat.locales`:
`scaffold` walks the enrolment sources (registry snapshots via the
authority, core enums, legal catalogue, topics, CLI tree introspection,
locale catalogues, plus Tier-A external seeds) and (1) preserves every
curated field on matched concepts verbatim, (2) creates scaffold-empty
entries for newly discovered enrolables with `lifecycle = draft` and empty
curated fields (no fuzzy auto-fill — the documented gettext failure mode),
(3) retires entries whose source vanished by stamping `lifecycle = retired`
+ `replaced_by`, never deleting. `set` / `relate` / `retire` verbs for
curation, `audit` for the health report, `scaffold --check` as the fast
drift gate in CI and pre-commit. Hand-editing curated prose fields directly
in fragments is permitted (registry-authoring precedent); structural
operations go through the CLI.

**D4 — Compiled search index unifies four record kinds** so the "pro rata"
query works end to end: (a) Handbook concept cards — definition,
short_description, aliases in four languages, legal grounding links; (b)
casilla projections — machine-generated at compile time from registry
snapshots (never hand-curated in the Handbook): modelo + casilla number +
localised description (the registry casilla label and per-revision locale
translations where authored, conforming to the official descriptions) +
legal_refs, deduplicated across revisions; (c) CLI surface records — every
command/option with its locale-resolved help; (d) the built documentation
pages themselves. Concepts are first-class palette results; casillas and
CLI verbs are searchable namespaces; pages are full-text. Each record kind
carries typed metadata (kind, modelo, language) for filtering and
weighting.

**D5 — Pagefind is the search backend.** At the established post-build
seam (the same lifecycle as the `docs/cli/` regeneration), a compiler in
`dev/docs/` renders the built HTML through Pagefind's `addDirectory` and
injects record kinds a-c via `addCustomRecord` with metadata, filters, and
ranking weights, emitting the chunked per-language index into the
uncommitted build output. The existing Ctrl-K palette is extended to query
Pagefind: term cards first (definition + jump links to glossary anchor,
casillas, legal corpus, how-tos), nav titles second, full text third. The
stock Sphinx search page is replaced by the Pagefind surface (Furo
template override; Gandi prior art). The Pagefind binary/wheel is vendored
and pinned. Orama is the documented fallback if vendoring fails.

**D6 — The dev RAG is the build-time compilation oracle: pre-run what a
runtime RAG does on the fly, ship the results as data.** The information
already exists — casilla and modelo definitions, crosslinked references,
legal grounding — embedded across the registry, the legal catalogue, the
corpus, the code, and the docs. The compilation step surfaces it by
running, ahead of time on the GPU dev box, the retrieval a reader-side RAG
would run live, and materialising the outputs. Four sub-decisions:

- *Query-vocabulary sweep.* The closed query vocabulary — every enrolled
  concept's preferred/admitted terms, four-language translations, hidden
  search forms, plus mined paraphrase candidates — is swept as semantic
  queries through the resident vaultspec-rag service (hybrid
  dense+sparse retrieval over the hardened index). Each sweep result is
  wrangled into a ranked documentation-target list per term. This is the
  precompiled term-to-result mapping: RAG capability frozen into data.
- *Index capability is a stated prerequisite.* The sweep is only as good
  as the index, so the RAG hardening track from the research graduates
  from recommendation to dependency: extraction sidecars for the
  PDF/XLS/XLSX grounding corpus (the Diseños de Registro workbooks
  first), text extraction for the normatives HTML (BOE
  article-delimiter-aware splitting), supported-extension additions
  (txt/xml/xsd/properties), and an explicit incremental reindex
  immediately before every sweep (the watcher staleness hole is
  documented).
- *Output wrangling is a typed transformation layer, not ad-hoc
  filtering.* Sweep outputs are raw chunk hits (file paths, line ranges,
  scores); the compiler resolves them through a chunk-to-target map:
  registry casilla fragments resolve to the casilla's projected search
  record; legal catalogue entries and corpus HTML resolve to the legal
  grounding surface; `src/aeat` modules resolve to their generated API
  stubs; docs sources resolve to built page anchors; CLI modules resolve
  to the generated CLI reference. Wrangling also applies the documented
  corrections: casilla-revision dedupe, locale-quadruplet collapse,
  score-floor and TOC-noise filtering, directory-cluster reading. Hits
  with no resolvable target are dropped and reported, never shipped
  half-mapped.
- *Sweep outputs are committed Handbook-layer data, SPLADE-free.* The
  ranked term-to-target relevance mappings and mined synonym candidates
  land as generated, reviewable data files in the Handbook tree —
  committed, because CI and the docs build have no GPU and no RAG
  service; the deterministic compiler consumes them as ranking weights
  for the Pagefind records (D5). Because the hybrid index's sparse half
  is SPLADE (CC BY-NC-SA), shipped derivatives must be laundered down to
  rankings and identifiers only — orderings and target ids, never stored
  vectors or sparse term-weight maps. Synonym candidates are ratified
  into the Handbook as `admitted` terms or `hidden_search_forms` through
  human review with relative-cosine validation — the
  allowlist-with-reason ratchet discipline the locales honesty gate
  established; unratified candidates stay in a review queue, never in
  the shipped index (antonym/co-hyponym intrusion: "deducible" vs "no
  deducible" must never alias). The sweep re-runs on cadence (registry
  or docs structure changes) and its diffs are reviewed like any
  generated-but-committed surface.

The static term-embedding matrix (rung 2, ~1-3 MB int8 over the closed
vocabulary, client-side cosine) is deferred behind a measured gate: build
a held-out real-query set, measure the miss-rate of the compiled mapping;
implement rung 2 only if misses are material. The browser transformer
(rung 3) is rejected.

**D7 — The generated glossary closes the redeclaration hole.** The
Handbook compiles to a generated glossary page (Sphinx `glossary`
directive output at the `builder-inited` seam, uncommitted like
`docs/cli/`), giving every approved concept a stable `:term:` anchor and
hover tooltips via sphinx-hoverxref (one term per entry — the shared-entry
tooltip bug). The existing nitpicky `-n -W` gate then enforces, for free:
every `:term:` reference resolves (missing enrolment breaks the build) and
no term is declared twice. Hand-written `docs/glossary.md` and the inline
"plain words you'll meet" sections are deleted in the same change
(no-legacy rule — no parallel hand-written copy survives). A new
docs-marked conformance test — the terminology sibling of the
command-conformance gates — scans MyST sources for prose re-declarations
of enrolled terms (definition-pattern matching against Handbook
short_descriptions) and fails on inline redefinition, steering authors to
`:term:` references.

**D8 — Gates, end to end:** handbook loader validation (unique ids, legal
refs resolve, lifecycle/replaced_by integrity, required short_descriptions
on approved concepts, relation targets exist); `scaffold --check` drift
gate; the `-n -W` glossary gate; the redeclaration gate; a compiled-index
smoke test (the worked example: "pro rata" returns the prorrata concept
card, at least one M303 prorrata casilla record, and the how-to page);
and the existing docs build/link gates unchanged. The committed sweep
outputs carry their own gates: every relevance mapping's term must be an
enrolled concept and every target must resolve in the current build (a
stale mapping fails loudly rather than shipping dead links), and a
licence gate asserts the shipped artefact contains only rankings and
identifiers — no vectors, no sparse term-weight maps. The Handbook enters
the `vaultspec-rag` dev index automatically (TOML is already walked), so
agent-side semantic search benefits immediately and the sweep can query
the Handbook's own concepts recursively.

**D9 — External seeding at scaffold time, Tier A only:** IATE TBX download
(es/hu/en, tax/law/finance domains, reliability ≥ 3), UBTERM fiscalitat
(ca/es/en, CC BY 3.0), EuroVoc SKOS labels (after licence verification on
the Publications Office download page). Every seeded value stamps
`seed_provenance` with the required attribution. AEAT/BOE/TAXUD sources
ground definitions by citation in `source` fields — transcription with
attribution, no bulk ingestion. ND/NC/unlicensed sources (TERMCAT open
downloads, RAE DPEJ, the TERMCAT/UOC IATE export, Microsoft Terminology)
are excluded from ingestion.

## Rationale

- **Why a committed Handbook rather than pure generation:** definitions,
  scope notes, alias ratification, and translation review are editorial
  judgement that no source emits; the operator mandates a continuously
  improved committed artefact. The msgmerge contract is the proven way to
  hold programmatic sync and human curation in one file set without
  clobbering (research P3); the project already runs this pattern twice
  (locales, apidocs).
- **Why concept-oriented TOML:** the term-first alternative breaks on
  multi-alias languages and missing locales (research P4); TOML fragments
  compiled to strict pydantic is the registry house pattern, the loader
  gives the validation seam, and the dev RAG indexes it for free.
- **Why Pagefind:** it is the only surveyed engine satisfying every hard
  constraint simultaneously — MIT, offline, es+ca+hu stemming with
  per-language splits, lazy chunked scaling, and a first-class API for
  injecting precompiled term records with weights (research P1). The
  uncommitted compiled index mirrors the operator's decision and the
  existing `docs/cli/` regeneration pattern exactly.
- **Why the RAG-as-oracle compilation:** a closed query vocabulary makes
  runtime retrieval unnecessary — every query a term card can answer is
  enumerable at build time, so the expensive half of RAG (embedding +
  hybrid retrieval) runs once on the dev box and ships as rankings. This
  is the only shape that delivers RAG-grade surfacing of the embedded
  registry/legal information under the offline, GPU-less, licence-clean
  shipping constraints; the laundering rule (rankings and identifiers
  only) is what keeps the SPLADE-tainted hybrid index usable as an
  oracle without tainting the shipped artefact.
- **Why rung-1 semantics:** declared four-language aliases already deliver
  cross-lingual matching declaratively; mined-ring intrusion risk is real
  in tax vocabulary and demands the human ratchet; rung 3's cost is
  disproportionate for a closed curated vocabulary (research P2). The
  rung-2 deferral is measurable, not speculative.
- **Why the glossary gate shape:** Sphinx `-n -W` already hard-breaks on
  unresolved and duplicate terms — the cheapest possible enrolment gate —
  and the surveyed ecosystems' universal governance gap (no redeclaration
  detection anywhere) confirms the conformance test must be ours
  (research P3).
- **Why casillas are projected, not curated:** their authoring home is the
  registry (labels, legal_refs, localisation), already validated by
  registry gates; duplicating 18,885 records into the Handbook would
  recreate the redeclaration disease this feature exists to cure.

## Consequences

- The four hand-maintained term stores collapse into one governed surface;
  terminology joins commands under codebase-state-as-truth. Docs authors
  write `:term:` references instead of inline definitions, and the build
  breaks when they do not.
- The reader gets one search that answers "what does pro rata mean", "which
  casillas does it touch", and "which command do I run" — offline, in four
  languages, with every result linked to its legal grounding.
- New maintenance loops, deliberately cheap: `scaffold --check` joins CI;
  curation debt is visible as `draft` concepts with empty
  short_descriptions (auditable, gateable); mined-synonym review is a
  recurring small task with a queue file.
- The Handbook will be large and its first scaffold run will create a
  curation backlog; tiering (concepts curated, casillas projected) bounds
  it, but the initial editorial pass over ~150-300 concepts is real work.
- Vendored Pagefind adds a pinned binary to the dev toolchain and a new
  post-build step to the docs pipeline; docs build time grows by the
  indexing pass (seconds to low minutes, not the Sphinx-build scale).
- The dev RAG graduates from optional tooling to a build-input dependency:
  the hardening track (sidecars, HTML extraction, extension coverage,
  reindex-before-sweep) becomes prerequisite work, and the committed sweep
  outputs add a generated-data review surface whose diffs must be read on
  every refresh. The compensating control is that CI and readers never
  touch the RAG — only its laundered, gated outputs.
- Casilla search quality in en/ca/hu is bounded by registry locale
  coverage; improving it routes through registry locale authoring, a
  separate workstream this ADR explicitly does not own.
- The palette and search-page rework touches shipped JS/templates; the
  existing palette's progressive-fallback design (terms → nav → full text)
  is preserved so degradation is graceful.
- Future pathways opened: the same Handbook can feed CLI help topics, the
  vault glossary references can be retired into it, and rung 2 has a
  measured on-ramp if rung-1 misses materialise.

## Codification candidates

- **Rule slug:** `terminology-single-declaration`.
  **Rule:** Every domain term surfaced in user docs is enrolled once in the
  Terminology Handbook and referenced via `:term:`; prose must never
  redeclare an enrolled term's definition inline, and hand-authored
  glossary surfaces are forbidden.
- **Rule slug:** `terminology-scaffold-preserve-contract`.
  **Rule:** Every Terminology Handbook scaffold run follows the
  three-outcome contract — preserve curated fields verbatim, scaffold new
  entries empty (no fuzzy auto-fill), retire vanished entries as
  tombstones with `replaced_by` — and never deletes a record.
- **Rule slug:** `shipped-search-licence-clean`.
  **Rule:** Artefacts shipped in or derived into the documentation search
  backend must come from licence-clean sources (no NC/ND/gated models or
  datasets); embedding-derived data ships only as plain, human-reviewed
  data files.
