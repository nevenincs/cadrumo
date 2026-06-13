---
tags:
  - '#research'
  - '#calculation-truth-inventory'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-01-post-restructure-audit]]'
  - '[[2026-05-01-corpus-data-hydration-review-audit]]'
---

# `calculation-truth-inventory` research: `modelo casilla tax rule and formula authority inventory`

This research inventories executable and committed-source locations that codify modelo identity, casilla definitions, tax/legal rules, calculation formulas, formula bindings, and rule-generation machinery. Generated documentation/build output and Python cache files are excluded. Committed JSON corpus locations are included only where they currently function as source data or generated projections that influence validation.

## Findings

### Central calculation and formula authority candidates

- `src/aeat/domain/calculations/_registry.py` centralizes `ALL_RULESETS` and `MODELO_REGISTRY`, validates modelo closure, legal citations, formula-id scoping, and catalogue target resolution.
- `src/aeat/domain/calculations/__init__.py` exports the central calculation registry.
- `src/aeat/domain/formulas/_formula.py` defines the formula AST, formula operands, formula bindings, casilla refs, parameter refs, decimal literal coercion, bracket formulas, rounding, and traversal helpers.
- `src/aeat/domain/formulas/_ruleset.py` defines `Ruleset`, `ParameterTable`, legal citation attachment, effective windows, computed-casilla closure, formula/casilla closure, parameter closure, and DAG validation.
- `src/aeat/domain/formulas/_registry.py` resolves applicable rulesets by modelo, period, and variant, and rejects duplicate or overlapping rule coverage.
- `src/aeat/domain/formulas/_engine.py` evaluates formulas and audits supplied casilla values against computed ledgers.
- `src/aeat/domain/formulas/_ledger.py` defines computation ledger, ledger entries, discrepancies, and audit reports.
- `src/aeat/domain/formulas/_period.py` defines fiscal period semantics.
- `src/aeat/domain/formulas/_codes.py` defines formula operation codes.
- `src/aeat/domain/formulas/_cli.py` exposes formula evaluation/audit CLI surfaces.
- `src/aeat/domain/formulas/__init__.py` exports the formula engine and registry surface.

### Concrete formula/ruleset modules

- `src/aeat/domain/formulas/_rulesets/__init__.py` imports and enumerates all registered rulesets in `ALL_RULESETS`; its docstring currently contains process-like coverage commentary and year-clone explanations.
- `src/aeat/domain/formulas/_rulesets/_common.py` defines the declarative authoring helpers for `casilla`, `formula`, `lit`, `ref`, `param`, arithmetic operators, percentage formulas, clamp, bracket constructors, and citations.
- `src/aeat/domain/formulas/_rulesets/_modelo_180_cumulation.py` encodes Modelo 180 cumulative-year behaviour.
- `src/aeat/domain/formulas/_rulesets/_mutators.py` encodes mutation-test operators over formulas.
- `src/aeat/domain/formulas/_rulesets/modelo_100_2024.py`, `modelo_100_2025.py`, `modelo_100_2026.py`, and `modelo_100_summary_2025.py` assemble Modelo 100 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_111_2024.py`, `modelo_111_2025.py`, and `modelo_111_2026.py` encode Modelo 111 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_115_2024.py`, `modelo_115_2025.py`, and `modelo_115_2026.py` encode Modelo 115 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_123_2024.py`, `modelo_123_2025.py`, and `modelo_123_2026.py` encode Modelo 123 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_130_2024.py`, `modelo_130_2025.py`, and `modelo_130_2026.py` encode Modelo 130 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_131_2024.py`, `modelo_131_2025.py`, and `modelo_131_2026.py` encode Modelo 131 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_180_2024.py`, `modelo_180_2025.py`, and `modelo_180_2026.py` encode Modelo 180 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_200_2024.py`, `modelo_200_2025.py`, `modelo_200_2026.py`, and `modelo_200_corporate_tax.py` encode Modelo 200 rulesets and corporate-tax helper logic.
- `src/aeat/domain/formulas/_rulesets/modelo_202_2025.py` encodes Modelo 202 rules.
- `src/aeat/domain/formulas/_rulesets/modelo_303_2024.py`, `modelo_303_2025.py`, and `modelo_303_2026.py` encode Modelo 303 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_390_2024.py`, `modelo_390_2025.py`, and `modelo_390_2026.py` encode Modelo 390 rulesets.
- `src/aeat/domain/formulas/_rulesets/modelo_100/_common.py`, `_amortization.py`, `_ccaa.py`, `_inventario.py`, and `_minimos.py` encode shared Modelo 100 legal/tax helpers.
- `src/aeat/domain/formulas/_rulesets/modelo_100/anexo_b1_2024.py`, `anexo_b1_2025.py`, `anexo_b1_2026.py`, `anexo_b2_2024.py`, `anexo_b2_2025.py`, `anexo_b2_2026.py`, `anexo_c_2024.py`, `anexo_c_2025.py`, `anexo_c_2026.py`, `anexo_d_ledgers.py`, `anexo_d_modulos_2024.py`, `anexo_d_modulos_2025.py`, `anexo_d_modulos_2026.py`, `anexo_d_normal_2024.py`, `anexo_d_normal_2025.py`, `anexo_d_normal_2026.py`, `anexo_d_simplificada_2024.py`, `anexo_d_simplificada_2025.py`, `anexo_d_simplificada_2026.py`, `anexo_e_2024.py`, `anexo_e_2025.py`, `anexo_e_2026.py`, `anexo_f_2024.py`, `anexo_f_2025.py`, `anexo_f_2026.py`, `anexo_g_2024.py`, `anexo_g_2025.py`, `anexo_g_2026.py`, `anexo_n_2024.py`, `anexo_n_2025.py`, and `anexo_n_2026.py` encode Modelo 100 anexo-specific formula/casilla logic.

### Modelo identity, cadence, applicability, and legal metadata

- `src/aeat/domain/modelos/_codes.py` defines the closed `ModeloCode` enum.
- `src/aeat/domain/modelos/_metadata.py` defines `ModeloMetadata`, including official name, display label, category, cadence, legal basis, applicability, cap relationships, related modelos, submission portal, and gotchas.
- `src/aeat/domain/modelos/_registry.py` imports per-modelo entries into `MODELO_REGISTRY`, validates coverage, validates cap relationships, and validates portal cross-references.
- `src/aeat/domain/modelos/_categories.py` defines modelo categories, cadences, citation source enums, and taxpayer profiles.
- `src/aeat/domain/modelos/_applicability.py` defines profile applicability.
- `src/aeat/domain/modelos/_citations.py` defines legal citation records.
- `src/aeat/domain/modelos/_citation_registry.py` defines known citation registry behaviour and citation validation.
- `src/aeat/domain/modelos/_entries/_common.py` builds modelo entries and citations.
- `src/aeat/domain/modelos/_entries/modelo_036.py`, `modelo_037.py`, `modelo_100.py`, `modelo_111.py`, `modelo_115.py`, `modelo_123.py`, `modelo_130.py`, `modelo_131.py`, `modelo_180.py`, `modelo_190.py`, `modelo_193.py`, `modelo_200.py`, `modelo_202.py`, `modelo_232.py`, `modelo_303.py`, `modelo_347.py`, `modelo_349.py`, `modelo_369.py`, `modelo_390.py`, `modelo_720.py`, and `modelo_840.py` each encode one modelo's official identity, legal basis, cadence, applicability, cap relationships, related modelos, and portal link.

### BOE and legal citation machinery missed by the first pass

- `src/aeat/domain/modelos/_citations.py` defines `LegalCitation` with source type, article, URL, quoted Spanish text, retrieval date, and `curated` status. This is a legal-evidence carrier, not a display-only object.
- `src/aeat/domain/modelos/_citation_registry.py` is a defensive legal-integrity layer. It rejects known bad citations for cuota diferencial, cuota íntegra estatal/autonómica, cuota líquida, Modelo 390 resumen anual, RIRPF retenciones, capital mobiliario, and other previously mis-cited formula areas.
- `src/aeat/domain/modelos/_categories.py` defines `LegalCitationSource`; this enum is consumed by modelo entries and formula rulesets to distinguish Ley, Real Decreto, Orden Ministerial, Reglamento, Manual práctico, and AEAT portal/help material.
- `src/aeat/domain/modelos/_entries/_common.py` is the shared modelo-entry citation builder and entry assembler.
- `src/aeat/domain/formulas/_rulesets/_common.py` defines `make_citation()` and the authoring helpers that attach legal citations directly to rulesets and computed casillas.
- `src/aeat/domain/formulas/_casilla.py` requires computed casillas to carry legal basis and explicitly treats primary legal/manual sources as mandatory evidence for executable computation.
- `src/aeat/domain/formulas/_rulesets/modelo_100/_common.py` pins Modelo 100 citation URLs to BOE consolidated texts for LIRPF, LIS, and RIRPF and stamps a retrieval date. The anexo modules consume `cite_lirpf()`, `cite_lis()`, and `cite_rirpf()`.
- `src/aeat/domain/formulas/_rulesets/modelo_100/_amortization.py` directly codifies the LIS article 12.1.a amortization table and names `BOE-A-2014-12328` as the statutory authority.
- `src/aeat/domain/formulas/_rulesets/modelo_100/_inventario.py` directly codifies inventory valuation behaviour from LIS article 17 and `BOE-A-2014-12328`.
- `src/aeat/domain/formulas/_rulesets/modelo_100/_ccaa.py` codifies autonomous-community tariff brackets and legal sources including Ley 22/2009, regional tax laws, year-dependent Asturias and Canarias changes, and exclusions for foral regimes and Ceuta/Melilla.
- The Modelo 100 anexo modules under `src/aeat/domain/formulas/_rulesets/modelo_100/` are not only formulas; they are legal-citation-bearing executable tax-law projections for IRPF income types, bases, reductions, minimos, cuotas, deductions, modules, and CCAA aggregation.
- `tests/import_contract/domain/formulas/_rulesets/test_all_rulesets_have_citations.py`, `src/aeat/domain/modelos/test_citation_registry.py`, `src/aeat/domain/modelos/test_citations.py`, and `src/aeat/domain/formulas/test_casilla_validator.py` encode the current citation integrity contract.

### Casilla schema, corpus access, and hydrate generation

- `src/aeat/domain/casillas/models.py` defines the committed casilla corpus schema: `CasillaDataType`, `PeriodType`, `FormulaReference`, `ValidationRuleReference`, `CasillaRecord`, `CasillaCatalogue`, review metadata, source metadata, and draft provenance.
- `src/aeat/domain/casillas/catalogue.py` reads, verifies, and writes `corpus/casillas` JSON; `save_casillas()` is the direct repository/corpus writer.
- `src/aeat/domain/casillas/__init__.py` exports the casilla model and catalogue surface.
- `src/aeat/domain/casillas/_hydrate/__init__.py` is the main hydrate entry point. It builds catalogues from rulesets and manual tables and still contains a write path through `run(..., write=True, root=...)`.
- `src/aeat/domain/casillas/_hydrate/records.py` converts rulesets/manual data into `CasillaRecord` rows, resolves rulesets, renders formula expressions, collects casilla refs, attaches `references_rules`, assigns periods, and applies Modelo 111 augmentation.
- `src/aeat/domain/casillas/_hydrate/data.py` contains hardcoded manual casilla tables for censal and informational modelos plus Modelo 111 augment data.
- `src/aeat/domain/casillas/_hydrate/metadata.py` generates source URLs, validation refs, section names, supported-language expansion, record payloads, and source metadata.
- `src/aeat/domain/casillas/_hydrate/formulas.py` renders formula AST nodes to expression strings and collects formula refs for corpus projection.
- `src/aeat/domain/casillas/_hydrate/lemmas.py` contains multilingual helper text fragments used by hydrate.
- `src/aeat/domain/casillas/_hydrate/constants.py` contains hydrate reviewer metadata and constants.
- `src/aeat/domain/casillas/_hydrate/models.py` defines the private `_Casilla` input model for hydrate manual tables.
- `src/aeat/entrypoints/cli/casillas.py` exposes `aeat app casillas hydrate`, `list`, `verify`, `extract`, and `translate`; the hydrate command is the operator-facing autogeneration surface.
- `corpus/casillas/modelo_*/<period>.json` currently codifies materialized casilla definitions, labels, help, formula expressions, `references_casillas`, `references_rules`, validation rules, source URLs, and review metadata. It is generated or curated data rather than executable code, but it behaves as a second authority today.

### Schema extraction and schema cache generation

- `src/aeat/domain/schema/_models.py` defines extracted schema IR for modelos, casillas, formula nodes, validation rules, schema provenance, and schema versioning. For `BOE_ORDEN` provenance it requires every casilla to carry `source_page`, requires `schema_version.boe_ref`, and requires it to match `provenance.document_ref`.
- `src/aeat/domain/schema/_enums.py` defines schema-level casilla/formula enums that overlap with casilla/formula concepts elsewhere.
- `src/aeat/domain/schema/_cache.py` reads and writes extracted schema cache JSON.
- `src/aeat/adapters/inbound/schema/_fetch.py` registers BOE Orden PDF sources in `BOE_ORDEN_SOURCES`, validates `boe_ref`, validates override URLs, fetches source PDFs, computes sha256/content length, and writes source PDFs into schema cache. The current Modelo 130 source entry explicitly says its `BOE-A-2023-15412` identifier is a placeholder pending human verification.
- `src/aeat/adapters/inbound/schema/_boe_extractor.py` parses BOE Orden PDFs into domain schema records and formula-like IR. It reads annex lines, detects casilla declarations, parses formula prose such as `Casilla A + Casilla B`, attaches `source_page`, and emits a `Modelo` with `SchemaProvenance(source=BOE_ORDEN)`. This is an autogeneration source for schema truth.
- `src/aeat/adapters/inbound/schema/testing.py` provides test helpers for schema extraction.
- `src/aeat/adapters/inbound/schema/test_fetch.py` and `test_boe_extractor.py` verify the fetch/extract path and should be rewritten as quarantine/extraction-review tests if BOE extraction remains.

### Filing builders and duplicate formula/casilla truth

- `src/aeat/domain/filing/_builders/modelo_130.py` contains hand-coded Modelo 130 draft calculations and casilla population parallel to the formula ruleset engine.
- `src/aeat/domain/filing/_builders/modelo_303.py` contains hand-coded Modelo 303 draft calculations and casilla population parallel to the formula ruleset engine.
- `src/aeat/domain/filing/_builders/modelo_390.py` contains hand-coded Modelo 390 draft calculations and casilla population parallel to the formula ruleset engine.
- `src/aeat/domain/filing/_builders/_modelo_130_schema.py`, `_modelo_303_schema.py`, and `_modelo_390_schema.py` define static filing schemas, required inputs, defaults, and descriptions that overlap with the ruleset and casilla corpus surfaces.
- `src/aeat/domain/filing/_builder.py`, `_schema.py`, `_validator.py`, and `_amendment.py` define filing draft structures, validation, and amendment behaviour using the builder outputs.
- `src/aeat/application/filing/_calculate.py` summarizes calculation status but does not itself encode formulas.
- `src/aeat/application/filing/_review.py` fingerprints schema/formula state and includes resolved ruleset identity in stale-approval logic.

### VAT rule, rate, classification, and Modelo 303 bridge truth

- `src/aeat/domain/vat/_schema.py` defines VAT categories, EU member states, VAT rates, citation source enums, citation records, legal references, and VAT strict models. `VATRegulation` requires citations and carries `boe_references` keyed to `aeat.domain.normatives`.
- `src/aeat/domain/vat/_rates.py` hardcodes EU VAT rate tables, including Spain 2024/2025 rates and BOE or Directive references.
- `src/aeat/domain/vat/_classification.py` classifies invoices/transactions into VAT categories.
- `src/aeat/domain/vat/_modelo_303_mapping.py` maps VAT categories and invoice direction to Modelo 303 casilla contributions.
- `src/aeat/domain/vat/_catalogue.py` defines the curated VAT catalogue, mostly backed by Ley 37/1992 (`BOE-A-1992-28740`) article citations, quoted or paraphrased Spanish text, and retrieval date.
- `src/aeat/domain/vat/_corpus.py` bridges VAT corpus loading with fallback to the hardcoded VAT catalogue.
- `src/aeat/domain/vat/_lookup.py` resolves VAT rates/categories.
- `src/aeat/domain/vat/_verify.py` verifies VAT catalogue/rate consistency and legal citation completeness.

### Spending categories, proportionality, and aggregation truth

- `src/aeat/domain/categories/_spending_category.py` defines the closed spending category enum.
- `src/aeat/domain/categories/_profile.py` defines category profile models and VAT hints.
- `src/aeat/domain/categories/_proportionality.py` defines deductibility/proportionality rules, statutory caps, citation models, and legal citation sources. `ProportionalityRule` requires at least one `CategoryCitation`.
- `src/aeat/domain/categories/_casilla_mapping.py` maps spending categories to modelo/casilla buckets and encodes cadence constraints.
- `src/aeat/domain/categories/_registry.py` hardcodes the 2025 category registry, citations, deductibility rules, proportionality rules, statutory caps, VAT hints, and casilla mappings. It embeds AEAT manual URLs, LIRPF BOE URL, RIRPF BOE URL, AEAT help URLs, short Spanish quotes, and casilla mappings into Modelo 130 and Modelo 303.
- `src/aeat/domain/categories/_corpus.py` attempts manual-backed loading but currently falls back to the hardcoded category registry.
- `src/aeat/application/aggregation/_models.py` defines aggregation inputs, casilla outputs, provenance, and decisions.
- `src/aeat/application/aggregation/_provider.py` defines aggregation provider contracts.
- `src/aeat/application/aggregation/_service.py` rolls classified transactions into AEAT casilla inputs using category/casilla mappings.

### Rental and Modelo 100 Anexo C truth

- `src/aeat/domain/rental/_models.py` defines rental data models that feed Modelo 100 Anexo C calculations.
- `src/aeat/domain/rental/_expense_rollup.py` calculates rental expense rollups.
- `src/aeat/domain/rental/_amortization_ledger.py` calculates amortization ledgers.
- `src/aeat/domain/rental/_anexo_c_aggregator.py` aggregates rental data into Anexo C casillas.
- `src/aeat/domain/rental/anexo_c_provider.py` merges caller-supplied and register-derived Anexo C casillas.
- `src/aeat/domain/rental/_tier_resolver.py` resolves rental tier/classification behaviour.

### Inbound declaration and borrador extraction truth

- `src/aeat/adapters/inbound/declaracion/_schema.py` defines parsed filing records, template revisions, extraction warnings, and extracted casilla records.
- `src/aeat/adapters/inbound/declaracion/_detect.py` detects declaration templates.
- `src/aeat/adapters/inbound/declaracion/_extractor.py` and `_generic_extractor.py` define extractor contracts and generic extraction logic.
- `src/aeat/adapters/inbound/declaracion/_extractors/modelo_036_v2025.py`, `modelo_037_v2025.py`, `modelo_111_v2025.py`, `modelo_115_v2025.py`, `modelo_123_v2025.py`, `modelo_130_v2025.py`, `modelo_131_v2025.py`, `modelo_180_v2025.py`, `modelo_190_v2025.py`, `modelo_193_v2025.py`, `modelo_200_v2025.py`, `modelo_202_v2025.py`, `modelo_232_v2025.py`, `modelo_303_v2024_09.py`, `modelo_303_v2025.py`, `modelo_347_v2025.py`, `modelo_349_v2025.py`, `modelo_369_v2025.py`, `modelo_390_v2025.py`, `modelo_720_v2025.py`, and `modelo_840_v2025.py` encode parser-side modelo/template revision IDs, casilla IDs, required casillas, label regexes, and extraction-specific structural checks.
- `src/aeat/adapters/inbound/declaracion/_parsers/modelo_100/_extractor.py` and `_scanner.py` encode Modelo 100 declaration extraction behaviour and casilla scanning.
- `src/aeat/adapters/inbound/borrador/_schema.py` defines Renta borrador records and summary casillas.
- `src/aeat/adapters/inbound/borrador/_tarifa.py` verifies Renta tariff casillas.
- `src/aeat/adapters/inbound/borrador/_extractors/modelo_100_summary_v2025.py` hardcodes Modelo 100 summary-block casilla IDs and regex extraction.

### Outbound export format and generated Python layout truth

- `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py` defines fixed-width record field specs, segment specs, validators, and casilla-to-wire layout primitives.
- `src/aeat/adapters/outbound/aeat/export/_formats/_serialise.py` serializes filing data into AEAT fixed-width export layouts.
- `src/aeat/adapters/outbound/aeat/export/_formats/_deserialise.py` parses export payloads back into structured records.
- `src/aeat/adapters/outbound/aeat/export/_formats/_ingest.py` ingests DR JSON specs into validated record specs and carries source metadata including `orden`, `boe_id`, `xlsx`, and `retrieval_date`.
- `src/aeat/adapters/outbound/aeat/export/_formats/_generate.py` writes generated Python modules from DR JSON specs and injects generated provenance into module docstrings. This is an explicit code-generation surface and should not be allowed to generate legal calculation rules.
- `src/aeat/adapters/outbound/aeat/export/_formats/modelo_130_2024.py`, `modelo_130_2025.py`, `modelo_303_2024.py`, `modelo_303_2024_preview.py`, and `modelo_303_2025.py` encode concrete export layout specs and field/casilla bindings.
- `tests/fixtures/dr_specs/mini_303.json` and `tests/fixtures/dr_specs/dr303e24.json` are committed source fixtures for export format generation. They embed BOE/Orden provenance such as `Orden HAC/819/2024` and `BOE-A-2024-16129`.
- `tests/fixtures/dr_specs/dr303e24.json` also carries transient generation notes with wave/process commentary and unresolved schema gaps. This is precisely the kind of development-process metadata that must not become part of legal/code truth.

### Legal source corpora and manual-backed truth

- `src/aeat/domain/normatives/_schema.py` defines `NormativeReference` and `Articulo`, including legal-act kind, number, title, publication date, canonical `boe_url`, `boe_id`, article permalink, tags, review date, and reviewer. It validates BOE ID shape and requires each article permalink to reference the parent BOE ID.
- `src/aeat/domain/normatives/_loader.py` loads `corpus/normatives/*.json` as a strict catalogue and rejects duplicate IDs or invalid records.
- `src/aeat/domain/normatives/_lookup.py` resolves normative references and articles by stable ID and article number.
- `src/aeat/domain/normatives/_cite.py` renders canonical citations such as Ley/Real Decreto/Orden plus article and BOE ID. This is the only sanctioned string renderer for normative citations in reports and logs.
- `src/aeat/domain/normatives/_verify.py` checks cross-record invariants including permalink alignment and rendered citation inclusion of BOE ID.
- `corpus/normatives/ley-35-2006.json`, `ley-37-1992.json`, `ley-58-2003.json`, `orden-hac-242-2025.json`, `rd-1065-2007.json`, `rd-1624-1992.json`, and `rd-439-2007.json` codify reviewed legal acts, articles, canonical BOE URLs, BOE IDs, article permalinks, publication dates, reviewer metadata, and Spanish summaries.
- `src/aeat/domain/manuals/_schema.py`, `_loader.py`, `_fetch.py`, `_ids.py`, and `_verify.py` define manual corpus IDs, schemas, loading, fetching, and verification. Manual rules can cite casillas, sibling sections, and external legal acts, and source records point back to manual URL, page, and paragraph.
- `src/aeat/domain/manuals/_fetch.py` hardcodes canonical AEAT PDF URLs in `PART_SPECS`, downloads raw PDFs, computes sha256/content length, and writes `manifest.json`. This is a materialization path for source evidence, not a calculation registry.
- `corpus/manuals/iva/2025/manifest.json`, `corpus/manuals/renta/2025/parte1/manifest.json`, and `corpus/manuals/renta/2025/parte2-deducciones-autonomicas/manifest.json` codify manual source manifests.

### Official AEAT record-design corpus now pulled locally

- `corpus/aeat_official/disenos_registro/manifest.json` is now the local top-level manifest for official AEAT record-design artefacts pulled from the Agencia Tributaria Sede Electronica `disenos-registro` pages.
- The pull was derived from the supported corpus surface under `corpus/casillas`, not from a hand-picked subset. The supported modelo set is `036`, `037`, `100`, `111`, `115`, `123`, `130`, `131`, `180`, `190`, `193`, `200`, `202`, `232`, `303`, `347`, `349`, `369`, `390`, `720`, and `840`.
- The official source pages used are the current and previous AEAT design-register indexes for `01-99`, `100-199`, `200-299`, `300-399`, and `resto modelos`.
- The local corpus contains 151 official artefacts across 20 supported modelos, with a zero-count manifest for `037` because no matching official record-design link was found on those index pages.
- Per-modelo counts are: `036:5`, `037:0`, `100:29`, `111:6`, `115:3`, `123:4`, `130:5`, `131:8`, `180:3`, `190:4`, `193:7`, `200:17`, `202:14`, `232:2`, `303:15`, `347:4`, `349:3`, `369:1`, `390:19`, `720:1`, and `840:1`.
- File-type coverage is `47` XLSX files, `25` XLS files, `54` PDF files, `15` XSD files, `12` properties dictionaries, and `1` DOCX file. Every artefact has a local byte count and SHA-256 in its modelo manifest.
- Validation performed after the pull confirmed that all 151 local artefacts match their manifest byte counts and SHA-256 hashes, no stored artefact is an HTML error page, all XLSX files are openable with `openpyxl`, XLS files have OLE signatures, PDFs have PDF signatures, XSD files expose XML schema headers, the DOCX file is a ZIP container, and properties files contain assignment data.
- The corpus proves that yearly and intra-year variation must be a first-class schema concern. Examples include Modelo 303 separate 2024 revisions for periods up to `08/2T` and from `09/3T`, Modelo 390 XSD/PDF/XLSX representation changes across years, Modelo 100 annual XSD/properties dictionaries, and Modelo 200 annual large XLS record designs.
- The official record-design corpus is filing-layout evidence, not calculation law by itself. It must be referenced by the registry as source evidence for casilla/export shape, while legal formulas, rates, thresholds, and applicability must also resolve to BOE/normative or official instruction/manual sources.

### Portal and deadline metadata that influences filing/cadence truth

- `src/aeat/domain/portals/_codes.py`, `_metadata.py`, `_registry.py`, `_categories.py`, and `_entries/portal_*.py` codify portal identity, related modelo links, and filing portal mappings.
- `src/aeat/domain/deadlines/_models.py`, `_engine.py`, `_calendar.py`, and `_applies.py` codify schedule/deadline rules and profile applicability that interact with modelo cadence.
- `src/aeat/domain/deadlines/_calendar.py` hardcodes supported years, filing windows, payment cutoff dates, known autónomo modelos, and opaque BOE/Manual citation keys.
- `src/aeat/domain/deadlines/_applies.py` hardcodes profile-applicability predicates for modelos 100, 111, 115, 130, 180, 190, 303, 347, 349, 390, and 720 with citation-key docstrings. This is executable obligation logic separate from modelo metadata and formulas.
- `src/aeat/domain/deadlines/_models.py` carries `boe_references` through emitted `FilingObligation` records.

### CLI surfaces that expose or mutate these domains

- `src/aeat/entrypoints/cli/casillas.py` exposes casilla load/verify/extract/translate/hydrate.
- `src/aeat/entrypoints/cli/categories.py` exposes category/casilla mapping views.
- `src/aeat/entrypoints/cli/financial/aggregate.py` exposes transaction-to-casilla aggregation.
- `src/aeat/entrypoints/cli/filing/__init__.py` exposes calculate/review/approve/export flows.
- `src/aeat/entrypoints/cli/_declaration.py` exposes declaration parse and formula audit surfaces.
- `src/aeat/entrypoints/cli/audit/_helpers.py` and `audit/__init__.py` expose legal-citation coverage checks over rulesets.
- `src/aeat/entrypoints/cli/normatives.py` exposes legal corpus lookup/verification.

### Test/import-contract surfaces that encode invariants and should be preserved or rewritten around the new source of truth

- `tests/import_contract/domain/formulas/_rulesets/test_all_rulesets_have_citations.py` enforces citation coverage.
- `src/aeat/domain/calculations/test_registry.py` enforces central registry scoping and legal basis.
- `src/aeat/domain/formulas/test_registry.py`, `test_engine.py`, `test_ruleset.py`, `test_formula.py`, `test_period.py`, and `test_casilla_validator.py` enforce formula/ruleset invariants.
- `src/aeat/domain/formulas/_rulesets/test_*.py` enforce per-modelo formula behaviour and mutation coverage.
- `src/aeat/domain/casillas/test_corpus_rule_alignment.py` currently enforces alignment between generated/committed casilla corpus, rulesets, extractors, and hydrate metadata.
- `src/aeat/domain/casillas/test_corpus_coverage.py` enforces corpus/ruleset coverage.
- `src/aeat/domain/modelos/test_registry.py`, `test_metadata.py`, `test_citation_registry.py`, `test_citations.py`, `test_applicability.py`, `test_casilla_cross_reference.py`, and `test_portal_cross_reference.py` enforce modelo metadata and cross-reference constraints.
- `src/aeat/domain/categories/test_registry.py` enforces category mappings against casilla IDs.
- `src/aeat/domain/vat/test_modelo_303_mapping.py`, `test_rules.py`, `test_verify.py`, and `test_classification.py` enforce VAT mapping/rate/classification behaviour.
- `src/aeat/adapters/outbound/aeat/export/_formats/test_ruleset_schema_coverage.py` and related export tests enforce export layout alignment.

### Generator and autogeneration surfaces requiring deletion or hard quarantine

- `src/aeat/domain/casillas/_hydrate/__init__.py` can generate and write casilla JSON projections.
- `src/aeat/domain/casillas/_hydrate/records.py` generates casilla records from rulesets and manual tables.
- `src/aeat/domain/casillas/_hydrate/data.py` is a manual hardcoded alternate source for casilla definitions.
- `src/aeat/domain/casillas/catalogue.py` contains `save_casillas()`, the generic corpus writer.
- `src/aeat/entrypoints/cli/casillas.py` exposes hydrate to the app CLI.
- `src/aeat/adapters/inbound/schema/_boe_extractor.py` generates schema IR from BOE PDFs.
- `src/aeat/domain/schema/_cache.py` persists generated schema cache JSON.
- `src/aeat/adapters/inbound/schema/_fetch.py` persists fetched source PDFs.
- `src/aeat/adapters/outbound/aeat/export/_formats/_generate.py` generates Python export format modules from DR JSON specs.
- `src/aeat/adapters/outbound/aeat/export/_formats/_ingest.py` ingests generation source specs.
- `tests/fixtures/dr_specs/*.json` currently act as generator source inputs.

### Generated or projection files with BOE references that are not legal authority

- `corpus/casillas/modelo_*/<period>.json` currently contains source URLs, source manual URLs, BOE references embedded in help text, formula expressions, validation refs, and review metadata. These files should be treated as generated projections or externalized review artifacts, not as an independent source of legal truth.
- `docs/_build/**` contains generated documentation output and must stay excluded from legal/code authority.
- `tests/fixtures/dr_specs/*.json` are committed fixtures and generation inputs for export layouts, not calculation law. They still carry BOE provenance and must be audited because generated Python modules copy that provenance into code docstrings.
- `src/aeat/adapters/outbound/aeat/export/_formats/modelo_130_2024.py`, `modelo_130_2025.py`, `modelo_303_2024.py`, `modelo_303_2024_preview.py`, and `modelo_303_2025.py` are code projections of export DR layout, not tax-calculation authority. They should depend on calculation truth for legal formula/casilla meaning, not define it.
- `src/aeat/domain/schema/_cache.py` output under the configured schema cache is a generated extraction artifact. If retained, it must be quarantined as evidence/review output and never imported as the source of executable calculation truth.

### Corrected interpretation after deeper read

- The earlier research was incomplete because it treated BOE and manual source references as a generic corpus layer. In the current codebase, legal citations are actively threaded through modelo metadata, rulesets, VAT rules, category proportionality, deadline obligations, schema extraction, and export-layout provenance.
- The current architecture has at least three kinds of legal material mixed together: primary source evidence (`corpus/normatives`, manual manifests, BOE PDF fetch records), executable legal projections (`formulas`, `vat`, `categories`, `deadlines`, `modelos`), and generated projections (`corpus/casillas`, schema cache, generated export modules).
- The BOE citation blocklist in `src/aeat/domain/modelos/_citation_registry.py` is especially important. It documents real prior citation errors and means the replacement architecture must preserve a negative-citation regression suite, not just positive citation presence.
- The export DR generator is not formula calculation truth, but it carries legal filing layout truth. The new architecture should keep it outside the calculation registry while enforcing that its casilla bindings resolve against the registry.
- The BOE schema extractor currently claims it can derive casilla/formula IR from Orden PDFs. That may be valuable as review evidence, but it is too unsafe to be an authority path unless every extracted rule is promoted through a human-reviewed registry record with BOE article/source references and regression tests.

### Cutover implications

- The current system does not have one source of legal truth. It has formula rulesets, modelo metadata entries, hydrate manual tables, committed casilla JSON, filing builder schemas, filing builder calculations, category mapping registries, VAT mapping/rate registries, extractor casilla maps, schema extraction/cache machinery, and export format generation.
- The most dangerous duplication is between `src/aeat/domain/formulas/_rulesets`, `src/aeat/domain/casillas/_hydrate`, `corpus/casillas`, `src/aeat/domain/filing/_builders`, `src/aeat/domain/schema`, `src/aeat/domain/deadlines`, `src/aeat/domain/vat`, and `src/aeat/domain/categories`.
- The hard cut should make `src/aeat/domain/calculations` the only place allowed to register legal calculation definitions. Other modules may consume it, project from it in memory, or validate external artifacts against it, but must not author, infer, or regenerate rule truth.
- Any generator that writes repository-owned truth must be removed from app CLI. If source extraction is retained, it must produce quarantined review artifacts, not authoritative code or legal rules.
- The central registry must distinguish authority classes: legal sources, calculation formulas, casilla definitions, modelo metadata, applicability/deadline rules, VAT/category classification rules, and export wire layouts. These may be related but must not shadow each other.
- The replacement test suite needs more than citation-presence checks. It needs BOE/normative reference validity, forbidden-citation regression, formula/casilla closure, generated-projection non-authority checks, export-layout binding checks, and real behavioural examples for each legal calculation path.

### Python module and library grounding after ADR review

- The replacement registry should live under `src/aeat/domain/calculations/registry/` because `src/aeat/domain/calculations/_registry.py` and `src/aeat/domain/calculations/__init__.py` are already the current calculation boundary. Creating `src/aeat/domain/registry/` would add another authority instead of eliminating shadowing.
- `src/aeat/domain/calculations/_registry.py` already treats the casilla corpus as a materialized view rather than calculation authority and validates modelo closure, required legal citations, formula-id scoping, and ruleset overlap through `RulesetRegistry`. That behaviour should be migrated into the new registry facade rather than retained as a parallel ruleset registry.
- `src/aeat/domain/formulas/_formula.py` is useful implementation evidence because it already uses Pydantic v2 discriminated unions, rejects float monetary literals, models formula AST nodes over `Decimal`, and avoids arbitrary string evaluation.
- `src/aeat/domain/formulas/_ruleset.py` is useful implementation evidence because it already validates parameter closure, casilla closure, computed-casilla closure, and DAG/cycle behaviour with `graphlib.TopologicalSorter`.
- `src/aeat/domain/formulas/_engine.py` is useful implementation evidence because it evaluates structured AST nodes with `Decimal`, explicit rounding, ledger entries, and discrepancy reporting. Those concepts should survive only as registry-backed runtime representations.
- `src/aeat/core/corpus_manifest/__init__.py` already provides SHA-256 and content-length integrity checks, path traversal rejection, deterministic canonical JSON, manifest self-attestation, and symlink exclusion. The new `_sources.py` should reuse or extend this integrity layer instead of creating a weaker parallel mechanism.
- `src/aeat/domain/modelos/_citation_registry.py` must be preserved as negative legal-citation regression evidence. It is not just citation coverage; it records known prior mis-citation classes and prevents recurrence.
- `src/aeat/domain/schema/_models.py` is useful as extracted-schema review evidence because it has strict Pydantic schema IR, source-page requirements, BOE provenance requirements, formula-like IR, and cycle checks. It should not survive as an authoritative calculation registry because it is a separate extracted projection.
- `src/aeat/adapters/outbound/aeat/export/_formats/_record_spec.py` is useful export-layout evidence because it models fixed-width field specs, segment specs, AEAT encodings, byte layout validation, overflow rejection, and monetary rounding. Generated export modules and DR JSON fixtures should be replaced by reviewed registry export definitions that reference official source artefacts.
- The project already targets Python 3.13 and has Pydantic v2 and `openpyxl` available. Standard-library `tomllib` is the correct read-only parser for authored TOML; `decimal.Decimal` remains the correct numeric basis for money and ratios; `graphlib.TopologicalSorter` remains suitable for formula and relation DAG validation; Pydantic v2 strict/frozen models should be the Python-side schema authority; Pydantic JSON Schema or JSON Schema 2020-12 can be derived for tooling but must not become the source of truth.
- `openpyxl` is appropriate for inspecting official XLSX record-design evidence. XML/XSD parsing with `lxml` or hardened XML tooling should remain an evidence-ingestion concern only, never an automatic legal-rule promotion path.

### Live AEAT cross-reference and remote-state guard research

- AEAT publishes an official `Simuladores` procedure page that currently lists Renta WEB Open, Sociedades WEB Open, Modelo 303 OPEN, Modelo 718 OPEN, and Modelo 390 OPEN. This proves that official Open simulator surfaces exist, but only for specific modelos and years. It does not prove that every supported modelo has a live read-only calculation surface.
- Renta WEB Open is explicitly described by AEAT as a simulator for IRPF that does not require taxpayer identification, does not validate the declarant NIF against the AEAT census, and does not allow filing the declaration. It may be researched as a read-only cross-reference surface for Modelo 100, subject to browser/network guards.
- Modelo 390 OPEN is explicitly described by AEAT as a simulator that does not require electronic identification, does not validate the declared NIF against the AEAT census, and does not allow filing the declaration. It may be researched as a read-only cross-reference surface for Modelo 390, subject to browser/network guards.
- Modelo 303's official procedure page lists a dedicated `Simulador 303 (OPEN)` alongside the authenticated `Presentación y servicio de ayuda Pre303` flow. The OPEN surface is the only candidate for live synthetic calculation checks. The authenticated Pre303/presentation surface is stateful filing infrastructure and must be treated as forbidden for development/demo calculation tests unless a later source proves an official read-only test mode.
- Sociedades WEB Open is described by AEAT as a non-authenticated simulator for Modelo 200 that can be used for checks prior to filing. AEAT also distinguishes it from the authenticated Sociedades WEB filing service; the filing service is not a safe development calculation oracle.
- AEAT has an official Integration environment for web-service testing, but the published page says it is authorized per web service, uses prepared test NIFs, and requires certificate details or an explicit test-environment request. This is not a general public formula oracle and cannot be assumed available for every modelo.
- AEAT record-design XLS/XLSX/PDF/XSD artefacts are official filing-layout evidence. AEAT's own record-design manual describes records, fields, positions, lengths, types, contents, notes, and per-year design variation. They are authoritative for export/import layout and may contain validation hints, but they are not sufficient by themselves as calculation law unless the specific artefact explicitly states a calculation or validation rule.
- AEAT instructions, manuals, and BOE normative references remain the filing-grade legal basis for formulas, rates, thresholds, filing conditions, and applicability. Live simulators can provide parity evidence, but they cannot replace BOE/AEAT legal source evidence in the registry.
- Live AEAT cross-reference must be classified per modelo revision as one of: official read-only Open simulator, official authorized Integration/test web service, static official documentation only, or forbidden authenticated/stateful surface. Unknown means forbidden until researched.
- The repository already contains no-write surfaces that are relevant evidence: `src/aeat/adapters/outbound/aeat/export/__init__.py` exposes only preflight/refusal contracts, `src/aeat/adapters/outbound/aeat/export/_submitters/__init__.py` intentionally exports no submitter surface, and `src/aeat/adapters/outbound/aeat/sede/test_no_write_surface.py` blocks write-shaped call contexts in the authenticated Sede adapter.
- The existing guards are not sufficient for the new architecture. The registry rebuild needs a central remote-state guard for live cross-reference work that rejects unsafe HTTP methods, unsafe AEAT hosts, authenticated filing portals, state-changing buttons/actions, server-side save flows, signing, presentation, payment, direct debit, amendment, cancellation, and document-submission paths.
- No live cross-reference test may use real taxpayer data, real filing drafts, real payment data, certificate-backed production submission flows, or authenticated portal state. Synthetic input is allowed only on official Open simulator surfaces or on an AEAT-authorized Integration service with test NIFs and explicit per-service evidence.
- Every model wave must include a live-AEAT surface decision, even when the decision is `static official documentation only` or `forbidden authenticated surface`. The decision must be recorded in the model-law coverage ledger with the official source URL, retrieval date, allowed operations, forbidden operations, and guard tests.

### XLS and XLSX calculation-parity evidence

- A local sample scan of the pulled official AEAT XLSX corpus found formula
  cells in the first 12 sampled XLSX files, including Modelo 303, Modelo 390,
  and Modelo 369 workbooks. The sample found `14,579` formula cells across
  those 12 workbooks.
- The largest sampled formula-bearing workbooks were Modelo 369
  (`3,040` formula cells), Modelo 390 2025 (`1,251` formula cells), Modelo 390
  2024 (`1,269` formula cells), and Modelo 303 2026 (`849` formula cells).
- A naive full-corpus XLSX formula scan timed out. The implementation needs a
  real indexed scanner with per-file timeouts, progress recording, formula-cell
  counting, sheet classification, error capture, and repeatable outputs.
- XLS/XLSX formula coverage may become the most complete practical parity
  surface for models whose official record-design spreadsheets contain
  executable formulas. That does not make the spreadsheet the legal authority.
  It makes the workbook a high-value AEAT source-evidence and parity oracle
  only after the formula cells are traced to official workbook files, workbook
  hashes, sheets, cells, and matching legal/source references.
- The scanner must classify each workbook as formula-bearing form, record-design
  layout, validation-hint workbook, static layout workbook, unsupported legacy
  binary XLS, or unreadable artefact. Unsupported does not mean ignored; it
  becomes an explicit coverage gap in the model-law ledger.
- Synthetic parity data must be generated once per modelo/revision and then
  applied identically to the registry calculation engine and to the official
  workbook/simulator parity surface. Divergence must produce a trace containing
  input facts, selected registry revision, workbook path and hash, sheet/cell
  addresses, expected workbook result, actual engine result, legal references,
  and source references.
- XLS binary files need a separate reader strategy from XLSX. The first safe
  implementation should support XLSX formula discovery with `openpyxl`; XLS
  support must be explicitly researched and may require conversion or a
  hardened parser before it can become a parity gate.
- The first backend verification pass against the local official AEAT workbook
  corpus discovered `72` workbook artefacts. A bounded scan of the first `25`
  artefacts classified `9` XLSX workbooks as formula-bearing, `16` binary XLS
  files as unsupported pending a reviewed parser/conversion path, and `0`
  artefacts as failed or timed out.
- A later verification found no local LibreOffice or `soffice` executable, but
  did find Excel COM automation registered locally. A synthetic XLSX smoke test
  opened a workbook read-only through Excel COM, injected inputs, recalculated,
  read the output cell, and closed without saving; the calculated output was
  `31.0` for `10 + 21`.
- Excel COM therefore provides a local workbook recalculation runner on this
  machine. The runner is acceptable only for local workbook parity; it does not
  touch AEAT remote state and must not be used for authenticated AEAT portal
  actions.
- A full corpus workbook classification pass with a `10` second per-file
  timeout scanned all `72` workbook artefacts: `47` XLSX workbooks were
  classified as formula-bearing, `25` binary XLS files were recorded as
  unsupported pending a safe parser/conversion path, and `0` artefacts failed.
