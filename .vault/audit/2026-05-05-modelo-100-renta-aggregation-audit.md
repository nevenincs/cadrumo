---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-04-21-modelo-100-renta-research]]'
  - '[[2026-04-27-modelo-100-renta-full-calc-research]]'
  - '[[2026-04-29-m100-per-ano-test-parity-research]]'
  - '[[2026-05-05-modelo-100-renta-source-dependency-reference]]'
---

# `modelo-100-renta-aggregation` audit

## Scope

Topic: Modelo 100 Renta aggregation under the central AEAT legal calculation
registry.

Audit surface: `registry/aeat`, `corpus/aeat_official/disenos_registro/modelo_100`,
`corpus/manuals/renta`, inbound borrador/declaracion parsers, outbound Sede
filed-data capture, rental domain modules, portal entries, category profiles,
tests, and older Modelo 100 vault documents.

Rewrite scope: ADR and plan direction plus the central registry scaffold,
construct schema, and focused registry tests for Modelo 100.

## Findings

- The central Modelo 100 registry authority now exists at
  `registry/aeat/modelos/100.toml`. It is still a scaffold: it owns source,
  revision, parity, Renta WEB Open, and initial dependency evidence, but it
  does not yet own final-settlement casillas or formulas.
- The official Modelo 100 record-design corpus exists locally under
  `corpus/aeat_official/disenos_registro/modelo_100`. Its manifest contains 29
  artefacts retrieved on 2026-05-03, including current ejercicio 2025
  dictionary, toma-de-datos dictionary, and XSD, historical 2020-2024
  dictionaries and XSDs, and 2009-2019 historical PDF/XLS artefacts.
- The AEAT current record-design page confirms ejercicio 2025 Modelo 100
  dictionary, toma-de-datos dictionary, and XSD artefacts updated on
  2026-04-14. The AEAT previous-years page confirms 2020-2024 dictionaries and
  XSDs, with 2023/2024 files updated in January 2026.
- The AEAT Modelo 100 procedure page confirms the live surfaces and legal
  anchors: Renta WEB/borrador, fiscal data, filed declaration consultation,
  Ley 35/2006, RD 439/2007, and Orden HAC/277/2026 approving ejercicio 2025
  Modelo 100 and related borrador/declaration procedures.
- The AEAT Renta 2025 manual corpus exists only for 2025 today:
  `corpus/manuals/renta/2025/parte1` and
  `corpus/manuals/renta/2025/parte2-deducciones-autonomicas`, with source PDF
  hashes in local manifests. The two Renta 2025 manual PDF payloads are now
  enrolled as reviewed source references and verified by the shared registry
  catalogue tests. Older supported ejercicios still need manual/legal source
  closure before a filing-grade revision can exist.
- Renta WEB Open is a safe candidate parity surface, not law. AEAT describes it
  as a simulator that requires no taxpayer identification, does not validate
  NIF, does not need fiscal data, and does not allow declaration presentation.
- Authenticated Renta WEB, fiscal-data, borrador, filed declaration, submitted
  file, declaration PDF, and justificante paths are observation surfaces only.
  The outbound Sede schema already models filed declaration artefacts and
  casillas as read-only observations, but Modelo 100 registry extraction
  profiles do not yet exist to enforce full revision coverage.
- The inbound borrador extractor currently provides a 2025 observed-value
  parser over printed four-digit casilla rows. It correctly states that it does
  not define Modelo 100 completeness, but it is still year-specific and not
  backed by a Modelo 100 registry profile.
- `src/aeat/domain/rental` contains real Renta-relevant logic and constants for
  rental aggregation, imputacion rates, art. 23.2 reduction tiers, dates, caps,
  and age thresholds. These are currently Python-owned legal calculation
  values. Under the ADR, they must become registry-declared constants and
  algorithm bindings or be deleted as authority.
- `registry/aeat/categories/profiles/2025.toml` contains Renta 2025 category
  proportionality guidance and many AEAT/manual references. It is useful source
  material, but it is not Modelo 100 authority and must not shadow
  `registry/aeat/modelos/100.toml`.
- The old Modelo 100 vault research/ADR/plan documents describe ruleset-era
  architecture, variant slots, issue-numbered work, and Python subpackages.
  Those documents are historical research inputs only. The current central
  registry ADR supersedes their implementation shape.
- The Modelo 100 source-dependency reference now records the official
  AEAT/BOE source families and dependency classifications that must be encoded
  into the registry before Renta can emit filing-grade output.
- The same reference now records the local 2020-2025 record-design coverage:
  each candidate supported ejercicio has a declaration dictionary,
  toma-de-datos dictionary, and XSD in the local AEAT manifest. The remaining
  source-ledger gaps are complete BOE article coverage by construct, CCAA legal
  coverage, and observation-surface classification.
- The BOE Modelo 100 ejercicio 2025 order is now present in the local corpus
  and registered in the shared source/legal catalogue as
  `boe-modelo-100-2025-form` and `orden-hac-277-2026:art-3`.
- `registry/aeat/modelos/100.toml` now exists as the Modelo 100 parent
  scaffold. It declares ejercicio 2020 through ejercicio 2025 revisions backed
  by official record-design source refs, record-design layout parity decisions,
  and initial ejercicio 2025 dependency relations to registered Modelos 111,
  115, 123, 130, 131, and 180. It does not yet contain Renta final-settlement
  casilla/formula coverage.
- Renta WEB Open is now present in the local AEAT corpus and registered as
  `aeat-renta-web-open`. Modelo 100 ejercicio 2025 declares it as an
  unauthenticated open-simulator parity surface with presentation, payment,
  signing, server-side save, amendment, cancellation, and document submission
  forbidden.
- The registry schema now has generic revision constructs. Modelo 100 ejercicio
  2025 uses `renta-source-foundation` for record-design/Renta WEB Open evidence
  and `renta-dependent-modelos` for the currently registered dependency
  bindings and relations. The validator rejects constructs that reference
  unknown revision members or fail to cover referenced member legal/source refs.
- Modelo 100 ejercicio 2025 now also declares `renta-payments-retentions` for
  the registered retentions and payments-on-account bindings and relations. It
  is not final settlement coverage; final casillas/formulas and observation
  reconciliation remain open.
- The first section constructs are now present for `renta-work-income`,
  `renta-real-estate-capital`, `renta-movable-capital`, and
  `renta-economic-activities`. They classify already registered dependency
  relations from Modelos 111, 115, 180, 123, 130, and 131. Missing annual
  summary modelos such as 190 and 193 remain blocked until they exist as
  central registry authorities.
- Modelo 100 ejercicio 2025 now declares `Consulta de declaraciones
  presentadas` as `modelo-100-filed-declarations-read`, an authenticated
  read-only observation surface backed by the local AEAT Modelo 100 procedure
  corpus. The registry guard allows only read methods, requires authentication
  and AEAT authorization, rejects synthetic data, and blocks presentation,
  signing, payment, server-side save, amendment, cancellation, and document
  submission.
- Some import-smoke tests still encode ADR-layout package names. They are not
  Modelo 100 functional tests and should be reviewed under the broader
  metastate-cleanup gate, but they are outside the Renta calculation backend
  itself.

## Required Work

- Create the Modelo 100 source ledger for each supported ejercicio before
  writing filing-grade registry content.
- Keep Modelo 100 source/legal catalogue enrollment under the shared registry
  consistency tests; Renta must not have a separate weaker verification path.
- Define the exact supported revision set. Current local source evidence is
  strongest for ejercicio 2020 through ejercicio 2025. Ejercicio 2026 cannot be
  represented as a Modelo 100 filing revision unless AEAT publishes official
  sources for that ejercicio.
- Create `registry/aeat/modelos/100.toml` as the only Modelo 100 authority.
- Move Renta constants, formula dependencies, casilla targets, CCAA parameters,
  rental/amortization/inventory legal values, parser coverage requirements, and
  live/static cross-reference decisions into reviewed registry data.
- Reduce inbound/outbound parsers to observation plumbing that requires registry
  extraction profiles and fails hard on coverage gaps.
- Keep Renta WEB Open parity read-only and guarded. Keep authenticated AEAT
  surfaces read-only and encrypted-observation-only.
- Add generalized tests for real registry loading, corpus source integrity,
  legal/source closure, revision selection, observation profile coverage,
  parser linkage, relation closure, and failure cases.
- Delete old authorities after replacement rather than leaving shims, aliases,
  compatibility rulesets, or duplicate metadata.

## Official Source URLs

- `https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G229.shtml`
- `https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html`
- `https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-100-199.html`
- `https://sede.agenciatributaria.gob.es/Sede/Ayuda/25Manual/100.html`
- `https://sede.agenciatributaria.gob.es/Sede/ayuda/consultas-informaticas/renta-ayuda-tecnica/renta-web-open.html`
