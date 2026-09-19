---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f90d21bd0294ea9419611e8aac9ed55a44a15888a49c3e26b7b2fc4458a4855c'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---
# `source-casilla-integration` research: `modelo 194 perceptor source lifecycle grounding`

This research establishes the exact M194 record-design evidence and the present source boundary. The official documents prove annual type-1 and repeatable type-2 filing destinations for three individually selected years, but do not identify a canonical pre-filing source fact, holder, acquisition route, provenance/absence semantics, or encrypted owner. It grounds a present no-current-candidate outcome; it does not classify required M194 facts as tax-inapplicable.

## Findings

### The only evidenced registry eras are three separate annual designs

The original approving Orden is BOE-A-1999-22309 (official XML, 78,941 bytes, SHA-256 `4db7f84c47a69fa48a315ae7e7f5655409b32aa6c2f224e80431a21dc8100b87`). BOE-A-2019-18752 Article 1 changes the type-2 transmission/amortisation/redemption/exchange/conversion value at positions 131--143; its final provision first applies to exercise 2019 filed in 2020 (official XML, 152,544 bytes, SHA-256 `824c0eaec1c3079b765ddb80a7ea4465746a6d8edf79f0cc9178d30d66505e62`). The AEAT historical design is `DR194_2016.pdf`, identifies exercise 2019, and is hash-pinned at 288,829 bytes and SHA-256 `792cd3ab3f1e94ce7afd62a6fa37710253aec7b801e3097ad27741f90a657d5a`.

BOE-A-2023-24412 Article 6 changes M194 declarant/perceptor identity, representative/province, and retention-related fields, first applying to exercise 2023 filed in 2024 (official XML SHA-256 `1b0fc692dbdd8d3e522838785cce59def4ecd9a4b1d077a80cdaddb855b2bd94`). The enrolled AEAT 2023 design is 148,101 bytes, SHA-256 `83cd9a332e0016607e87332bea8c3e5d33f0b0f8373ec56f820d82414ca76a7b`. BOE-A-2024-27528 Article 1 changes type-1 support and prior-declaration receipt fields plus type-2 retention percentage, first applying to exercise 2024 filed in 2025 (official XML, 134,485 bytes, SHA-256 `9ad47835e73b3136a9d300a833da9efa59d126c5825653e547d10990653be11e`); its enrolled AEAT design is 183,268 bytes, SHA-256 `4a738a126ddb465aac236b687aa25441b7cb71ec4b0ef6ea940096a3747b2651`.

The loaded registry selects exactly `2019`, `2023`, and `2024`, each annual `0A`; 2020--2022 and 2025 onward refuse. Current or historic catalogue presence is not evidence that one PDF's values, bytes, or source semantics continue into another year.

### The official record establishes a repeatable filing row, not a canonical source lifecycle

Each selected design has one type-1 declarant record and type-2 perceptor records. Type-1 summary counts explicitly count type-2 rows, including repeated appearances of one perceptor. The type-2 surface includes declarant/perceptor and representative identity, origin and code, accrual year, acquisition/subscription and transmission/amortisation/redemption/exchange/conversion values, signed withholding base, rate, and withheld amount. The 2024 design says the acquisition/subscription value is the one appearing in a supporting certificate, but does not identify a Cadrumo-acquirable canonical holder, document ingress contract, durable event identity, duplication/absence/correction rule, or secure owner.

That distinction is material. A static record design tells a filer where facts must be emitted; it does not demonstrate the pre-filing fact's authoritative provenance or a lossless source grain. The documented value transformations and sign/rounding surface cannot be inferred from a summary total, record coordinate, or generic repeated-record transport.

### Existing paths remain direct manual summary input and non-substitutable withholding machinery

Every selected M194 snapshot is applicability-grade and has exactly five direct-manual `resumen` casillas (`01`--`05`), no bindings, formulas, extraction profiles, or export layouts. The manual boxes are genuine direct operator inputs and remain distinct from a type-2 source lifecycle. Application links name downstream consumers but create neither M194 source values nor an owner.

Exact repository scans found no M194 source-connectivity census row, source-mesh resolver, secure M194 repository, ingress parser, binding, filing-producer namespace, semantic map, renderer, or source-owned export. The existing `WithholdingObservation` family is explicitly a Modelo 190/193 perceptor-retention contract. Its fact set does not carry M194's origin-dependent acquisition/transmission values or the M194 type-2 identity and row semantics; extending it from a shared word such as `retenciÃ³n` would drop or invent facts rather than establish ownership.

### Filing transport, post-filing reads, and design parsing are not value acquisition

AEAT's Modelo 194 procedure offers presentation by file and historical consultation/cancellation. Those are filing transport and post-filing read paths. The local extracted design and summary-parity tests read official layout evidence only. Neither route identifies an upstream source, proves capture provenance, or provides a non-lossy encrypted fact owner, so neither may be promoted into a source candidate or reused as a data-acquisition contract.

## Current evidence boundary

The current evidence does not establish the predicate required to create a source-connectivity candidate: a canonical source fact and holder, native fact grain and durable identity, destination map, acquisition provenance plus absence/duplicate/correction semantics, and a secure non-lossy owner. This leaves all five direct-manual summaries, the separate exact-year selector refusals, and the filing/export boundary intact.

A later source step can revisit M194 only after evidence identifies those acquisition and ownership facts, maps them one selected era at a time to type-1/type-2 destinations with sign/unit/rounding/aggregation rules, and proves encrypted persistence, replay, review, and any supported source-owned export independently from the filing transport.

## Sources

- https://www.boe.es/buscar/doc.php?id=BOE-A-1999-22309
- https://www.boe.es/buscar/doc.php?id=BOE-A-2019-18752
- https://www.boe.es/buscar/doc.php?id=BOE-A-2023-24412
- https://www.boe.es/buscar/doc.php?id=BOE-A-2024-27528
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-100-199.html
- https://sede.agenciatributaria.gob.es/Sede/irpf/retenciones-ingresos-cuenta-pagos-fraccionados/retenciones-ingresos-cuenta/modelo-194.html
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/manifest.json`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/files/02-194-diseno-de-registro-actualizado-en-2023.pdf.extracted.md`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/files/01-194-diseno-de-registro-actualizado-en-2024.pdf.extracted.md`
- `src/cadrumo/_data/registry/aeat/modelos/194/`
- `src/cadrumo/domain/calculations/registry/_withholding_bindings.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_187_188_194_registry.py`
- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-194-design-era-coverage-reference.md`
- `.vault/audit/2026-08-25-registry-temporal-coverage-s47-m194-era-review-audit.md`
