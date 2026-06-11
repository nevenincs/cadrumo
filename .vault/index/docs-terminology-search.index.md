---
generated: true
tags:
  - '#index'
  - '#docs-terminology-search'
date: '2026-06-11'
related:
  - '[[2026-06-10-docs-terminology-search-W01-P01-S01]]'
  - '[[2026-06-10-docs-terminology-search-W01-P01-S02]]'
  - '[[2026-06-10-docs-terminology-search-W01-P02-S03]]'
  - '[[2026-06-10-docs-terminology-search-W01-P02-S04]]'
  - '[[2026-06-10-docs-terminology-search-W01-P02-S05]]'
  - '[[2026-06-10-docs-terminology-search-W01-P02-S06]]'
  - '[[2026-06-10-docs-terminology-search-W01-P03-S07]]'
  - '[[2026-06-10-docs-terminology-search-W01-P03-S08]]'
  - '[[2026-06-10-docs-terminology-search-W02-P04-S09]]'
  - '[[2026-06-10-docs-terminology-search-W02-P04-S10]]'
  - '[[2026-06-10-docs-terminology-search-W02-P05-S11]]'
  - '[[2026-06-10-docs-terminology-search-W02-P05-S12]]'
  - '[[2026-06-10-docs-terminology-search-W02-P06-S13]]'
  - '[[2026-06-10-docs-terminology-search-W02-P06-S14]]'
  - '[[2026-06-10-docs-terminology-search-W03-P07-S15]]'
  - '[[2026-06-10-docs-terminology-search-W03-P07-S16]]'
  - '[[2026-06-10-docs-terminology-search-W03-P08-S17]]'
  - '[[2026-06-10-docs-terminology-search-W03-P08-S18]]'
  - '[[2026-06-10-docs-terminology-search-W03-P09-S19]]'
  - '[[2026-06-10-docs-terminology-search-W03-P09-S20]]'
  - '[[2026-06-10-docs-terminology-search-W03-P09-S21]]'
  - '[[2026-06-10-docs-terminology-search-W04-P10-S22]]'
  - '[[2026-06-10-docs-terminology-search-W04-P10-S23]]'
  - '[[2026-06-10-docs-terminology-search-W04-P11-S24]]'
  - '[[2026-06-10-docs-terminology-search-W04-P12-S25]]'
  - '[[2026-06-10-docs-terminology-search-W04-P12-S26]]'
  - '[[2026-06-10-docs-terminology-search-W04-P12-S27]]'
  - '[[2026-06-10-docs-terminology-search-W04-P12-S28]]'
  - '[[2026-06-10-docs-terminology-search-W05-P13-S29]]'
  - '[[2026-06-10-docs-terminology-search-W05-P13-S30]]'
  - '[[2026-06-10-docs-terminology-search-W05-P14-S31]]'
  - '[[2026-06-10-docs-terminology-search-W05-P14-S32]]'
  - '[[2026-06-10-docs-terminology-search-adr]]'
  - '[[2026-06-10-docs-terminology-search-plan]]'
  - '[[2026-06-10-docs-terminology-search-research]]'
  - '[[2026-06-11-docs-terminology-search-audit]]'
  - '[[2026-06-11-docs-terminology-search-code-review-audit]]'
  - '[[2026-06-11-docs-terminology-search-reconciliation-audit]]'
  - '[[2026-06-12-docs-terminology-search-rung2-adjudication-audit]]'
---

# `docs-terminology-search` feature index

Auto-generated index of all documents tagged with `#docs-terminology-search`.

## Documents

### adr

- `2026-06-10-docs-terminology-search-adr` - `docs-terminology-search` adr: `terminology handbook and precompiled docs search` | (**status:** `accepted`)

### audit

- `2026-06-11-docs-terminology-search-audit` - `docs-terminology-search` audit: `umbrella gap-concept curation pass`
- `2026-06-11-docs-terminology-search-code-review-audit` - `docs-terminology-search` Code Review
- `2026-06-11-docs-terminology-search-reconciliation-audit` - `docs-terminology-search` audit: `plan exec reconciliation`
- `2026-06-12-docs-terminology-search-rung2-adjudication-audit` - `docs-terminology-search` audit: `rung-2 adjudication`

### exec

- `2026-06-10-docs-terminology-search-W01-P01-S01` - Deliver the upstream kick-off brief to the vaultspec-rag team requesting generic preprocess hook infrastructure - per-project file-pattern-to-preprocessor registration, a versioned preprocess output schema (extracted text or pre-chunked units with source metadata), cache invalidation keyed on source content hash plus preprocessor identity and version, explicit hard-fail versus skip-and-report failure semantics, and watcher/incremental integration - and track the upstream issue reference back into this plan (ADR D6)
- `2026-06-10-docs-terminology-search-W01-P01-S02` - Adjudicate and document the interim path while the upstream hook is pending: a committed extraction-sidecar tree mirroring the existing corpus/manuals source-extraction convention, consumed by the existing walker, with the explicit retirement trigger being the upstream hook landing (ADR D6)
- `2026-06-10-docs-terminology-search-W01-P02-S03` - Implement the BOE normatives HTML-to-text preprocessor splitting on the BOE article delimiter and stripping TOC link farms, emitting schema-conformant output (or interim sidecars) for the 13 MB normatives corpus (ADR D6)
- `2026-06-10-docs-terminology-search-W01-P02-S04` - Implement the Disenos de Registro workbook extractor (openpyxl) over the 74 xlsx plus 28 xls official AEAT files, materialising the casilla-number to field-position tables as schema-conformant text - the highest-value grounding surface (ADR D6)
- `2026-06-10-docs-terminology-search-W01-P02-S05` - Implement PDF text extraction over the 73 corpus manual/instruction PDFs including the over-10MB tail, emitting schema-conformant output with per-file provenance (ADR D6)
- `2026-06-10-docs-terminology-search-W01-P02-S06` - Close the unsupported-text-extension tail (txt, xml, xsd, properties - 36 files incl. M349 instructions and the M100 diccionario dictionaries) via the upstream extension map or interim sidecar emission (ADR D6)
- `2026-06-10-docs-terminology-search-W01-P03-S07` - Add the explicit incremental reindex-before-sweep step to the compile pipeline and a coverage gate asserting every supported-type file under src/aeat/_data is present in the code index metadata, closing the documented watcher staleness hole (ADR D6)
- `2026-06-10-docs-terminology-search-W01-P03-S08` - Build the golden-query retrieval verification sweep (prorrata, casilla labels, disposicion transitoria, Disenos field positions, four-language probes) asserting hits land on the preprocessed surfaces above an agreed score floor before sweep outputs are trusted (ADR D6)
- `2026-06-10-docs-terminology-search-W02-P04-S09` - Implement the typed concept-oriented records (concept level: immutable Spanish-stem concept_id, closed domain enum, domain_refs, legal_refs, broader/related with narrower derived, lifecycle draft/approved/deprecated/retired, replaced_by, seed_provenance, dates
- `2026-06-10-docs-terminology-search-W02-P04-S10` - Implement the loader validation gates: unique never-reused ids, every legal_ref resolves in the legal catalogue, relation targets exist, lifecycle/replaced_by integrity (retired requires replacement), approved concepts carry a grounded es definition with source citation and short_descriptions in every authored language section (ADR D2/D8)
- `2026-06-10-docs-terminology-search-W02-P05-S11` - Implement the scaffold verb walking every enrolment source (registry snapshots via the validated authority, core enums, legal catalogue, topics, CLI tree introspection, locale catalogues) under the msgmerge three-outcome contract: preserve curated fields verbatim, scaffold new enrolables as empty drafts with no fuzzy auto-fill, retire vanished entries as tombstones with replaced_by (ADR D3)
- `2026-06-10-docs-terminology-search-W02-P05-S12` - Implement the curation verbs (set, relate, retire), the audit health report (draft counts, empty short_descriptions, unresolved relations, seed provenance coverage), and scaffold --check as the fast drift gate wired into CI and pre-commit (ADR D3/D8)
- `2026-06-10-docs-terminology-search-W02-P06-S13` - Run the first scaffold and editorially migrate the four hand-maintained term stores (the shipped glossary page, the explanation inline mini-glossary, the two vault glossary references) into the initial curated concept set of roughly 150-300 approved concepts, tiering casillas out as projections per ADR D4 (ADR D1)
- `2026-06-10-docs-terminology-search-W02-P06-S14` - Implement Tier-A seed importers - IATE TBX download (es/hu/en, tax/law/finance domains, reliability at least 3) and UBTERM fiscalitat (ca/es/en, CC BY 3.0), EuroVoc labels only after licence verification - stamping seed_provenance with the required attribution on every seeded value and excluding all ND/NC/unlicensed sources (ADR D9)
- `2026-06-10-docs-terminology-search-W03-P07-S15` - Implement the casilla projection compiler: per-modelo casilla search records from registry snapshots via the validated authority (modelo, casilla number, localised label/description including per-revision locale fragments where authored - conforming to the official casilla descriptions - plus legal_refs), deduplicated across revisions, never hand-curated (ADR D4)
- `2026-06-10-docs-terminology-search-W03-P07-S16` - Implement the CLI-surface record emitter (every command and option with locale-resolved help across the four languages) and the concept-card emitter (definition, short_description, four-language alias sets, legal grounding links) (ADR D4)
- `2026-06-10-docs-terminology-search-W03-P08-S17` - Implement the typed chunk-to-target resolution map: registry casilla fragments resolve to their projected records, legal catalogue entries and corpus HTML to the legal grounding surface anchors, src/aeat modules to generated API stubs, docs sources to built page anchors, CLI modules to the generated CLI reference
- `2026-06-10-docs-terminology-search-W03-P08-S18` - Implement the wrangling corrections layer as tested code: casilla-revision dedupe, locale-quadruplet collapse, score-floor and TOC-noise filtering, directory-cluster reading (ADR D6)
- `2026-06-10-docs-terminology-search-W03-P09-S19` - Implement the query-vocabulary sweep runner: every enrolled concept's terms, translations, and hidden forms swept through the resident RAG service (port 8766, timeout 30, reindex-before-sweep per W01.P03) into ranked term-to-target relevance mappings, with a cadence re-run verb whose diffs are reviewed like any generated-but-committed surface (ADR D6)
- `2026-06-10-docs-terminology-search-W03-P09-S20` - Land the committed relevance data files in the Handbook tree with their gates: every mapped term is an enrolled concept, every target resolves in the current build (stale mappings fail loudly), and the laundering/licence gate asserts the shipped artifact carries rankings and identifiers only - no vectors, no sparse term-weight maps, no SPLADE-derived data (ADR D6/D8)
- `2026-06-10-docs-terminology-search-W03-P09-S21` - Implement synonym-candidate mining with relative-cosine validation and the ratification queue: ratified candidates land in the Handbook as admitted terms or hidden_search_forms through human review under the allowlist-with-reason ratchet
- `2026-06-10-docs-terminology-search-W04-P10-S22` - Vendor and pin the Pagefind binary/wheel for the offline-hermetic build and add the post-build index pass over the built HTML (addDirectory), keeping the nitpicky Sphinx gate untouched
- `2026-06-10-docs-terminology-search-W04-P10-S23` - Inject the compiled record kinds via the Pagefind indexing API (addCustomRecord: concepts, casilla projections, CLI records) with typed metadata, filters, and ranking weights derived from the committed relevance data
- `2026-06-10-docs-terminology-search-W04-P11-S24` - Extend the Ctrl-K palette to query Pagefind with the progressive ladder - term cards first (short_description plus jump links to glossary anchor, casillas, legal corpus, how-tos), nav titles second, full text third - and replace the stock search page with the Pagefind surface via Furo template override (ADR D5)
- `2026-06-10-docs-terminology-search-W04-P12-S25` - Generate the glossary page from approved Handbook concepts at the builder-inited seam (uncommitted, like the CLI reference), one term per entry, with term anchors and hover tooltips via sphinx-hoverxref (ADR D7)
- `2026-06-10-docs-terminology-search-W04-P12-S26` - Delete the hand-written glossary page, the explanation mini-glossary, and every inline term re-definition in the same change, converting prose to term-role references so the nitpicky build gate enforces enrolment and single declaration (ADR D7, no-legacy rule)
- `2026-06-10-docs-terminology-search-W04-P12-S27` - Implement the redeclaration conformance gate - the terminology sibling of the command-conformance gates - scanning MyST sources for prose re-declarations of enrolled terms and failing on inline redefinition (ADR D7/D8)
- `2026-06-10-docs-terminology-search-W04-P12-S28` - Land the end-to-end smoke gate: the offline prorrata worked example returns the concept card, at least one M303 prorrata casilla record, and the relevant how-to page, plus four-language query checks (ADR D8)
- `2026-06-10-docs-terminology-search-W05-P13-S29` - Implement the curation-backlog honesty ratchet: draft-concept and empty-short_description counts gated non-increasing in CI with a standing review cadence, mirroring the locale translation-honesty discipline (ADR D3 consequence)
- `2026-06-10-docs-terminology-search-W05-P13-S30` - Build the held-out real-query miss-rate harness over the compiled mapping and adjudicate the deferred rung-2 static term-embedding matrix on measurements, persisting the adjudication in the vault (ADR D6 deferral gate)
- `2026-06-10-docs-terminology-search-W05-P14-S31` - Enrol this epic's own architectural vocabulary (Terminology Handbook, sweep, projection, relevance mapping, preprocess hook, laundering, record kinds) as Handbook concepts so build teams cross-reference the ADR definitions through the shipped surface, and keep ADR decision ids D1-D9 cited in every exec record (operator mandate)
- `2026-06-10-docs-terminology-search-W05-P14-S32` - Run the campaign honesty review before structural completion is declared and promote the three ADR codification candidates (terminology-single-declaration, terminology-scaffold-preserve-contract, shipped-search-licence-clean) through the codify phase

### plan

- `2026-06-10-docs-terminology-search-plan` - `docs-terminology-search` `terminology handbook and precompiled docs search epic` plan

### research

- `2026-06-10-docs-terminology-search-research` - `docs-terminology-search` research: `precompiled docs terminology search backend`
