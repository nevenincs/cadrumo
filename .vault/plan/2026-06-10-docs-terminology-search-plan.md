---
tags:
  - '#plan'
  - '#docs-terminology-search'
date: '2026-06-10'
tier: L4
related:
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-research]]'
---








# `docs-terminology-search` `terminology handbook and precompiled docs search epic` plan

## Epic intent

Build the three-layer terminology architecture accepted in 2026-06-10-docs-terminology-search-adr: enrolment sources (registry, legal catalogue, enums, CLI tree, locales) feed a committed, programmatically scaffolded, continuously curated Terminology Handbook (the middle layer between registry compilation and shipped documentation), which compiles - together with a build-time RAG sweep that pre-runs what a runtime RAG does on the fly - into uncommitted shipped search artifacts (Pagefind index, generated glossary, palette term cards). Strategic goals: one governed terminology surface replacing four unsynchronised hand stores; one offline quad-lingual search answering concept lookups (what does pro rata mean), casilla schema lookups (localised official-conforming descriptions plus legal grounding), and CLI navigation in a single ranked result set; and a generic document-preprocessing contract pushed upstream to the vaultspec-rag team (preprocess hook infrastructure with a well-defined preprocess schema) so PDF/XLS/HTML grounding corpora become indexable without project-specific knowledge leaking upstream. Every Step cites the ADR decision (D1-D9) it implements so build teams can cross-reference the architectural definitions; the Handbook enrols this epic's own architectural vocabulary so the cross-referencing surface is self-hosting. External PM association: the docs-terminology-search epic on the chore/eliminate-shims factory branch, backed by 2026-06-10-docs-terminology-search-adr (a GitHub milestone should be opened to mirror it; the W01 upstream kick-off additionally tracks a vaultspec-rag issue reference). Timeline: multi-wave, coordinator-orchestrated with per-step code-review gates; W01 unblocks the W03 sweeps; W02 unblocks everything Handbook-shaped; W04 is the user-visible cutover; W05 is standing.


## Wave `W01` - RAG preprocessing capability and index hardening

ADR D6 prerequisite graduated to delivery: generalise document preprocessing through an upstream vaultspec-rag preprocess-hook contract (file-pattern-to-preprocessor registration plus a versioned preprocess output schema), implement the project-side BOE/AEAT preprocessors (PDF, XLS/XLSX, normatives HTML) as plugins or interim sidecars, close the supported-extension and staleness gaps, and verify retrieval quality over the hardened index. Nothing in W03 sweeps until this wave proves coverage.

### Phase `W01.P01` - Upstream preprocess-hook contract (vaultspec-rag team)

Hand the generic requirements upstream and keep this project unblocked: the vaultspec-rag team receives a kick-off brief for preprocess hook infrastructure (per-project file-pattern-to-preprocessor registration, a versioned preprocess output schema, cache keying on source hash plus preprocessor identity, explicit failure semantics, watcher integration); the project adjudicates the interim path so W03 never stalls on upstream cadence. ADR D6 index-capability prerequisite.

- [ ] `W01.P01.S01` - Deliver the upstream kick-off brief to the vaultspec-rag team requesting generic preprocess hook infrastructure - per-project file-pattern-to-preprocessor registration, a versioned preprocess output schema (extracted text or pre-chunked units with source metadata), cache invalidation keyed on source content hash plus preprocessor identity and version, explicit hard-fail versus skip-and-report failure semantics, and watcher/incremental integration - and track the upstream issue reference back into this plan (ADR D6); `.vault/exec record + upstream vaultspec-rag issue tracker`.
- [x] `W01.P01.S02` - Adjudicate and document the interim path while the upstream hook is pending: a committed extraction-sidecar tree mirroring the existing corpus/manuals source-extraction convention, consumed by the existing walker, with the explicit retirement trigger being the upstream hook landing (ADR D6); `.vault/exec record + src/aeat/_data/corpus layout`.

### Phase `W01.P02` - Project-side document preprocessors

The BOE/AEAT-specific extraction logic stays project-side as preprocessors conforming to the upstream schema (or emitting interim sidecars): normatives HTML, Disenos de Registro workbooks, corpus PDF manuals, and the small unsupported-text-extension tail. ADR D6 preprocessing/transformation.

- [ ] `W01.P02.S03` - Implement the BOE normatives HTML-to-text preprocessor splitting on the BOE article delimiter and stripping TOC link farms, emitting schema-conformant output (or interim sidecars) for the 13 MB normatives corpus (ADR D6); `dev preprocessing tooling + src/aeat/_data/corpus/normatives`.
- [ ] `W01.P02.S04` - Implement the Disenos de Registro workbook extractor (openpyxl) over the 74 xlsx plus 28 xls official AEAT files, materialising the casilla-number to field-position tables as schema-conformant text - the highest-value grounding surface (ADR D6); `dev preprocessing tooling + src/aeat/_data/corpus/aeat_official/disenos_registro`.
- [ ] `W01.P02.S05` - Implement PDF text extraction over the 73 corpus manual/instruction PDFs including the over-10MB tail, emitting schema-conformant output with per-file provenance (ADR D6); `dev preprocessing tooling + src/aeat/_data/corpus manuals and aeat_official`.
- [ ] `W01.P02.S06` - Close the unsupported-text-extension tail (txt, xml, xsd, properties - 36 files incl. M349 instructions and the M100 diccionario dictionaries) via the upstream extension map or interim sidecar emission (ADR D6); `upstream request + dev preprocessing tooling`.

### Phase `W01.P03` - Index freshness and retrieval verification

Close the documented staleness hole, make reindex-before-sweep a pipeline step, and prove retrieval quality over the hardened index with golden queries before any sweep output is trusted. ADR D6.

- [ ] `W01.P03.S07` - Add the explicit incremental reindex-before-sweep step to the compile pipeline and a coverage gate asserting every supported-type file under src/aeat/_data is present in the code index metadata, closing the documented watcher staleness hole (ADR D6); `dev compile pipeline + RAG service discipline`.
- [ ] `W01.P03.S08` - Build the golden-query retrieval verification sweep (prorrata, casilla labels, disposicion transitoria, Disenos field positions, four-language probes) asserting hits land on the preprocessed surfaces above an agreed score floor before sweep outputs are trusted (ADR D6); `dev tests for retrieval verification`.

## Wave `W02` - Terminology Handbook foundation

ADR D1-D3: the committed TOML authoring tree under src/aeat/_data/terminology, the strict concept-oriented schema and loader (TBX/SKOS subset), the aeat.terminology CLI with the msgmerge three-outcome scaffold contract (preserve / scaffold-empty / retire-tombstone), drift and validation gates, bootstrap enrolment migrating the four hand-maintained term stores, and licence-clean Tier-A external seeding (IATE, UBTERM).

### Phase `W02.P04` - Concept schema and loader

ADR D2: the typed concept-oriented record model (concept / language section / term section, TBX-SKOS subset) and the strict TOML loader with its validation seam, following the registry authoring-compiler house pattern.

- [x] `W02.P04.S09` - Implement the typed concept-oriented records (concept level: immutable Spanish-stem concept_id, closed domain enum, domain_refs, legal_refs, broader/related with narrower derived, lifecycle draft/approved/deprecated/retired, replaced_by, seed_provenance, dates; `language sections es/en/ca/hu: definition, source citation, scope_note, required first-class short_description; term sections: label, term_status preferred/admitted/deprecated/forbidden, hidden_search_forms, grammatical fields) plus the strict TOML loader (ADR D2); `src/aeat terminology package + src/aeat/_data/terminology tree`.
- [x] `W02.P04.S10` - Implement the loader validation gates: unique never-reused ids, every legal_ref resolves in the legal catalogue, relation targets exist, lifecycle/replaced_by integrity (retired requires replacement), approved concepts carry a grounded es definition with source citation and short_descriptions in every authored language section (ADR D2/D8); `terminology loader + its tests folder`.

### Phase `W02.P05` - aeat.terminology CLI with the msgmerge contract

ADR D3: the scaffold verb with the three-outcome contract over every enrolment source, curation verbs, the audit health report, and scaffold --check as the fast drift gate in CI and pre-commit, mirroring the aeat.locales discipline.

- [ ] `W02.P05.S11` - Implement the scaffold verb walking every enrolment source (registry snapshots via the validated authority, core enums, legal catalogue, topics, CLI tree introspection, locale catalogues) under the msgmerge three-outcome contract: preserve curated fields verbatim, scaffold new enrolables as empty drafts with no fuzzy auto-fill, retire vanished entries as tombstones with replaced_by (ADR D3); `aeat.terminology CLI scaffold verb`.
- [ ] `W02.P05.S12` - Implement the curation verbs (set, relate, retire), the audit health report (draft counts, empty short_descriptions, unresolved relations, seed provenance coverage), and scaffold --check as the fast drift gate wired into CI and pre-commit (ADR D3/D8); `aeat.terminology CLI + CI wiring`.

### Phase `W02.P06` - Bootstrap enrolment, store migration, external seeds

ADR D1/D9: the first scaffold run, editorial migration of the four hand-maintained term stores into curated concepts (casillas tiered out as projections), and licence-clean Tier-A seeding with per-record provenance attribution.

- [ ] `W02.P06.S13` - Run the first scaffold and editorially migrate the four hand-maintained term stores (the shipped glossary page, the explanation inline mini-glossary, the two vault glossary references) into the initial curated concept set of roughly 150-300 approved concepts, tiering casillas out as projections per ADR D4 (ADR D1); `src/aeat/_data/terminology tree + editorial pass`.
- [ ] `W02.P06.S14` - Implement Tier-A seed importers - IATE TBX download (es/hu/en, tax/law/finance domains, reliability at least 3) and UBTERM fiscalitat (ca/es/en, CC BY 3.0), EuroVoc labels only after licence verification - stamping seed_provenance with the required attribution on every seeded value and excluding all ND/NC/unlicensed sources (ADR D9); `aeat.terminology seed importers + licence notes`.

## Wave `W03` - Compilation pipeline: projections, wrangling, RAG sweep

ADR D4 and D6: the deterministic record projections (casilla records with localised official-conforming descriptions, CLI surface records, concept cards), the typed chunk-to-target resolution map and output-wrangling layer, and the build-time RAG sweep that freezes runtime-RAG capability into committed, laundered, gated relevance data plus the synonym-mining ratification loop.

### Phase `W03.P07` - Deterministic record projections

ADR D4: the four record kinds compiled deterministically - concept cards, casilla projections carrying the localised official-conforming descriptions and legal_refs from registry snapshots (never hand-curated), and CLI surface records with locale-resolved help.

- [ ] `W03.P07.S15` - Implement the casilla projection compiler: per-modelo casilla search records from registry snapshots via the validated authority (modelo, casilla number, localised label/description including per-revision locale fragments where authored - conforming to the official casilla descriptions - plus legal_refs), deduplicated across revisions, never hand-curated (ADR D4); `dev docs terminology compiler`.
- [ ] `W03.P07.S16` - Implement the CLI-surface record emitter (every command and option with locale-resolved help across the four languages) and the concept-card emitter (definition, short_description, four-language alias sets, legal grounding links) (ADR D4); `dev docs terminology compiler`.

### Phase `W03.P08` - Chunk-to-target resolution and output wrangling

ADR D6 output wrangling as a typed transformation layer: RAG chunk hits resolve to documentation targets through an explicit map; unresolvable hits drop loudly; the documented corrections (revision dedupe, locale collapse, noise floors) are tested code, not ad-hoc filtering.

- [ ] `W03.P08.S17` - Implement the typed chunk-to-target resolution map: registry casilla fragments resolve to their projected records, legal catalogue entries and corpus HTML to the legal grounding surface anchors, src/aeat modules to generated API stubs, docs sources to built page anchors, CLI modules to the generated CLI reference; `unresolvable hits are dropped and reported, never shipped half-mapped (ADR D6); `dev docs terminology compiler`.
- [ ] `W03.P08.S18` - Implement the wrangling corrections layer as tested code: casilla-revision dedupe, locale-quadruplet collapse, score-floor and TOC-noise filtering, directory-cluster reading (ADR D6); `dev docs terminology compiler tests`.

### Phase `W03.P09` - RAG sweep and committed relevance data

ADR D6 core: the query-vocabulary sweep through the resident service freezes runtime-RAG retrieval into committed Handbook-layer relevance data, laundered to rankings and identifiers only (SPLADE taint excluded), with the synonym-mining ratification queue under the allowlist ratchet.

- [ ] `W03.P09.S19` - Implement the query-vocabulary sweep runner: every enrolled concept's terms, translations, and hidden forms swept through the resident RAG service (port 8766, timeout 30, reindex-before-sweep per W01.P03) into ranked term-to-target relevance mappings, with a cadence re-run verb whose diffs are reviewed like any generated-but-committed surface (ADR D6); `dev docs sweep runner`.
- [ ] `W03.P09.S20` - Land the committed relevance data files in the Handbook tree with their gates: every mapped term is an enrolled concept, every target resolves in the current build (stale mappings fail loudly), and the laundering/licence gate asserts the shipped artifact carries rankings and identifiers only - no vectors, no sparse term-weight maps, no SPLADE-derived data (ADR D6/D8); `src/aeat/_data/terminology relevance tree + gates`.
- [ ] `W03.P09.S21` - Implement synonym-candidate mining with relative-cosine validation and the ratification queue: ratified candidates land in the Handbook as admitted terms or hidden_search_forms through human review under the allowlist-with-reason ratchet; `unratified candidates never reach the shipped index (ADR D6); `dev docs mining + Handbook ratification queue`.

## Wave `W04` - Shipped search surface and glossary cutover

ADR D5 and D7: vendored Pagefind post-build indexing with injected custom records, the palette and search-page integration (term cards first, nav second, full text third), the generated glossary with term anchors and hover tooltips, deletion of every hand-maintained glossary surface in the same change, the novel redeclaration conformance gate, and the end-to-end prorrata smoke gate.

### Phase `W04.P10` - Pagefind integration

ADR D5: vendored, pinned Pagefind indexing the built HTML post-build and ingesting the injected custom records (concepts, casillas, CLI) with metadata, filters, and relevance-derived ranking weights; per-language index splits verified for es/en/ca/hu.

- [ ] `W04.P10.S22` - Vendor and pin the Pagefind binary/wheel for the offline-hermetic build and add the post-build index pass over the built HTML (addDirectory), keeping the nitpicky Sphinx gate untouched; `document the Orama fallback trigger (ADR D5); `dev docs build pipeline + dependency pinning`.
- [ ] `W04.P10.S23` - Inject the compiled record kinds via the Pagefind indexing API (addCustomRecord: concepts, casilla projections, CLI records) with typed metadata, filters, and ranking weights derived from the committed relevance data; `verify per-language index splits for es/en/ca/hu (ADR D5/D4); `dev docs pagefind integration`.

### Phase `W04.P11` - Palette and search page

ADR D5: the existing Ctrl-K palette queries Pagefind with the progressive ladder (term cards, then nav titles, then full text) and the stock Sphinx search page is replaced by the Pagefind surface via Furo template override.

- [ ] `W04.P11.S24` - Extend the Ctrl-K palette to query Pagefind with the progressive ladder - term cards first (short_description plus jump links to glossary anchor, casillas, legal corpus, how-tos), nav titles second, full text third - and replace the stock search page with the Pagefind surface via Furo template override (ADR D5); `docs/_static/aeat-docs.js + docs/_templates + docs/conf.py`.

### Phase `W04.P12` - Generated glossary, hand-store deletion, conformance gates

ADR D7: the generated glossary with term anchors and hover tooltips lands at the builder-inited seam; every hand-maintained glossary surface is deleted in the same change per the no-legacy rule; the novel redeclaration gate and the prorrata end-to-end smoke gate close the wave.

- [ ] `W04.P12.S25` - Generate the glossary page from approved Handbook concepts at the builder-inited seam (uncommitted, like the CLI reference), one term per entry, with term anchors and hover tooltips via sphinx-hoverxref (ADR D7); `docs/conf.py + dev docs generator`.
- [ ] `W04.P12.S26` - Delete the hand-written glossary page, the explanation mini-glossary, and every inline term re-definition in the same change, converting prose to term-role references so the nitpicky build gate enforces enrolment and single declaration (ADR D7, no-legacy rule); `docs tree editorial cutover`.
- [ ] `W04.P12.S27` - Implement the redeclaration conformance gate - the terminology sibling of the command-conformance gates - scanning MyST sources for prose re-declarations of enrolled terms and failing on inline redefinition (ADR D7/D8); `docs conformance test suite`.
- [ ] `W04.P12.S28` - Land the end-to-end smoke gate: the offline prorrata worked example returns the concept card, at least one M303 prorrata casilla record, and the relevant how-to page, plus four-language query checks (ADR D8); `docs conformance test suite`.

## Wave `W05` - Continuous improvement and cross-reference governance

Standing wave per the operator mandate: curation-backlog ratchets, the measured rung-2 adjudication harness, self-hosting enrolment of this epic's own architectural vocabulary so build teams cross-reference ADR definitions through the shipped surface, and the campaign honesty review plus codify pass on the three ADR codification candidates.

### Phase `W05.P13` - Curation and measurement loops

Standing loops: the curation-backlog honesty ratchet over draft concepts and empty short descriptions, and the held-out real-query miss-rate harness that adjudicates the deferred rung-2 static term-embedding matrix with measurements instead of speculation. ADR D6 deferral gate.

- [ ] `W05.P13.S29` - Implement the curation-backlog honesty ratchet: draft-concept and empty-short_description counts gated non-increasing in CI with a standing review cadence, mirroring the locale translation-honesty discipline (ADR D3 consequence); `terminology audit gate + CI`.
- [ ] `W05.P13.S30` - Build the held-out real-query miss-rate harness over the compiled mapping and adjudicate the deferred rung-2 static term-embedding matrix on measurements, persisting the adjudication in the vault (ADR D6 deferral gate); `dev docs tests + .vault adjudication record`.

### Phase `W05.P14` - Architectural cross-reference coverage and codification

Operator mandate: enrol this epic's own architectural vocabulary so ADR definitions are cross-referenceable through the shipped surface by every build team; run the campaign honesty review; promote the three ADR codification candidates through the codify phase.

- [ ] `W05.P14.S31` - Enrol this epic's own architectural vocabulary (Terminology Handbook, sweep, projection, relevance mapping, preprocess hook, laundering, record kinds) as Handbook concepts so build teams cross-reference the ADR definitions through the shipped surface, and keep ADR decision ids D1-D9 cited in every exec record (operator mandate); `src/aeat/_data/terminology tree + .vault exec discipline`.
- [ ] `W05.P14.S32` - Run the campaign honesty review before structural completion is declared and promote the three ADR codification candidates (terminology-single-declaration, terminology-scaffold-preserve-contract, shipped-search-licence-clean) through the codify phase; `.vault audit + .vaultspec rules pipeline`.

## Description

This epic implements the accepted `docs-terminology-search` ADR. The ADR's
decision identifiers are the shared vocabulary of this plan: every Step
cites the decision it implements, and build teams MUST read the cited
decision before executing a Step - the ADR carries the architectural
definitions (Terminology Handbook, record kinds, sweep, wrangling,
laundering, tombstone, ratification queue) that the Step text uses as
terms of art.

Decision-to-wave coverage map (completeness check - every ADR decision is
owned by at least one wave):

| ADR decision | Owning waves |
| --- | --- |
| D1 Handbook authoring tree (committed middle layer) | W02 |
| D2 Concept-oriented schema | W02.P04 |
| D3 msgmerge scaffold contract + CLI | W02.P05, W05.P13 |
| D4 Four unified record kinds | W03.P07, W04.P10 |
| D5 Pagefind backend + palette | W04.P10, W04.P11 |
| D6 RAG-as-oracle compilation (capability, preprocessing, wrangling, committed sweep outputs) | W01 (prerequisite), W03.P08, W03.P09, W05.P13 |
| D7 Generated glossary + redeclaration gates | W04.P12 |
| D8 End-to-end gate inventory | W02.P04, W03.P09, W04.P12 |
| D9 Licence-clean external seeding | W02.P06 |

Layer boundaries to hold during execution: enrolment sources are read
through their existing authorities (registry snapshots via the validated
authority, enums by import, CLI by introspection) - never re-parsed; the
Handbook tree and the committed relevance/ratification data are the ONLY
new committed surfaces; everything compiled for the reader (Pagefind
index, generated glossary, term cards) is uncommitted build output,
mirroring the generated CLI reference. The upstream vaultspec-rag
kick-off (W01.P01.S01) is deliberately generic - file-pattern-to-
preprocessor registration against a versioned preprocess output schema -
because BOE/AEAT specifics are this project's plugins, not upstream
features; S02's interim sidecar path guarantees the epic never blocks on
upstream cadence.

## Parallelization

- W01 and W02 are independent and can run concurrently from day one
  (different teams: RAG-infrastructure vs Handbook foundation).
- Inside W01: P01 (upstream contract) and P02 (project-side
  preprocessors) parallelize; P03 verification requires P02 outputs.
- Inside W02: P04 then P05 are sequential (CLI consumes the loader); P06
  requires both; the P06 editorial migration parallelizes across
  documents once the first scaffold lands.
- W03 requires W02.P04/P05 (records to project, concepts to sweep) and
  W01 complete (index trustworthy); inside W03, P07 and P08 parallelize,
  P09 consumes both.
- W04 requires W03 outputs for ranking weights (P10/S23) but P10/S22
  (vendoring) and P11 palette scaffolding can start once W02 exists;
  P12's cutover (S26) is strictly last in the wave - deletion only lands
  together with the generated replacement.
- W05 is standing and overlaps everything after W02; S31 (self-hosting
  vocabulary) can land as soon as the Handbook accepts concepts.
- Shared-worktree discipline applies: before dispatching any Step, grep
  git log for prior landings; before first edit to a file, diff for peer
  WIP; re-read HEAD before acting on findings.

## Verification

- Per-step: the cited ADR decision's constraints are the review rubric;
  vaultspec-code-review gates every landing per the house pipeline.
- W01 exit: golden-query retrieval sweep (S08) green over preprocessed
  surfaces; coverage gate (S07) reports zero supported-type `_data` files
  absent from the index.
- W02 exit: loader validation gates green; `scaffold --check` green in
  CI; the four hand stores have migrated concepts enrolled (the stores
  themselves are deleted later, in W04.P12.S26); seeded records carry
  provenance.
- W03 exit: relevance-data gates green (enrolled terms, resolving
  targets, laundering assertions); ratification queue operational with
  zero unratified candidates shipped.
- W04 exit: nitpicky docs build green with the generated glossary and
  term-role conversions; redeclaration gate green; the offline prorrata
  smoke gate (S28) returns concept card + M303 casilla + how-to in one
  ranked result set; four-language probes pass; no hand glossary surface
  remains.
- Epic exit: W05.P14.S32 honesty review run BEFORE structural completion
  is declared (campaign-close rule), codification candidates adjudicated,
  and the curation ratchet + miss-rate harness installed as standing CI
  surfaces.
