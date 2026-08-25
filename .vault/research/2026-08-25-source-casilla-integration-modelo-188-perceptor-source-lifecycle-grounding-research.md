---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:553dd5d369537628713be3b64358aadc0400732dcaaf9152c1cd57fdc3191140'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-25-source-casilla-integration-modelo-188-perceptor-source-owner-deferral-adr]]'
---
# `source-casilla-integration` research: `modelo 188 perceptor source lifecycle grounding`

This research establishes the factual boundary for Modelo 188's only selected
current era, `2023-y-siguientes` with annual period `0A`.  Official authority
proves a declarant-led annual summary and repeatable perceptor record, but the
current application has neither an insurer/perceptor fact carrier nor a
source-to-destination lifecycle.  It records no disposition: the model-scoped
ADR must decide whether the resulting gap blocks connection while preserving
the five existing manual summary targets.

## Findings

### The exact selected era is 2023 onwards, not a backdated historic design

BOE-A-1999-22372 originally approved Modelo 188's annual summary, perceptor
sheets, and Annex-V physical/logical design.  Its type-2 detail changed in
BOE-A-2017-15845, applicable first to declarations for exercise 2017, and
again in BOE-A-2023-24412 Article 5: declarant NIF plus the perceptor NIF,
legal-representative NIF, and province fields.  The latter applies first to
informative declarations for exercise 2023, filed in 2024.

The current AEAT catalogue labels Modelo 188 as Orden EHA/3021/2007 updated by
Orden HFP/1284/2023.  The bundled primary record design is exactly the
106,418-byte `DR_Mod_188_2023.pdf`, SHA-256
`30ced236b558de21383c3eba6339cb720fc9a704d38eaa574dd9be55cf90f9e3`.
The law-selected registry consequently refuses 2019--2022 and selects only
`2023-y-siguientes/0A`; the 2023 design cannot evidence an earlier record's
bytes or fact semantics.

### The 2023 design establishes individual perceptor facts, not merely five totals

The type-1 record declares the filing party and summary values.  The type-2
record has its own perceptor/representative identity and domicile attributes,
modality, signed capital-income amount, additional information, reductions,
withholding base, rate, withheld amount, accrual exercise, and key.  Its
summary counts and bases explicitly aggregate type-2 rows by the positive or
negative/zero withholding-base split; the same perceptor may appear more than
once.  Therefore a lossless source lifecycle needs a durable perceptor-row
identity, a distinct absence/zero/correction rule, and the row valuesâ€”not a
single summary total, a static layout position, or generic repeated-record
transport.

### Existing M188 registry support is a manual summary surface, not a source owner

The loaded `188/2023-y-siguientes/0A` snapshot is applicability-grade.  It has
five manual `resumen` casillas (`01`--`05`) and no bindings, formulas, export
layouts, or extraction profiles.  The narrow parity test confirms only their
five summary spans in the current design.  Its application-link catalogue
names consumers but does not create values, an issuer/perceptor carrier, or a
resolver.

The five direct manual summary targets are genuine existing registry paths and
must remain distinct from a proposed source lifecycle.  They cannot preserve
an individual perceptor's identity, row multiplicity, modality, retention
calculation context, or correction/absence semantics.  Conversely, this
research finds no M188-specific manual row input, parser, secure repository,
source-mesh resolver, producer values, or canonical connectivity-census row.

### Presentation and historic read surfaces do not acquire the filing facts

AEAT's live procedure exposes 2025 presentation by file and 2020-onward
consultation/cancellation; those are filing and post-filing read routes.  The
record design, export coordinates, and any parsed filed declaration describe
where or what was sent, not the pre-filing insurer/declarant acquisition,
perceptor-row grain, durable source identity, or encrypted provenance of a new
calculation value.  Existing generic filing-observation storage is likewise
not M188 evidence and cannot turn a record design into a source owner.

The remaining ADR question is narrow: whether the authentic external
insurer/declarant type-2 perceptor fact family should remain explicitly blocked
until one approved secure owner can preserve the full native row, while the
current manual summary targets and the independently governed historic/export
boundaries remain unchanged.

## Sources

- https://www.boe.es/buscar/doc.php?id=BOE-A-1999-22372
- https://www.boe.es/buscar/doc.php?id=BOE-A-2017-15845
- https://www.boe.es/buscar/doc.php?id=BOE-A-2023-24412
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI08.shtml
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_188/manifest.json:1`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_188/files/01-188-diseno-de-registro-actualizado-en-2023.pdf.extracted.md:1`
- `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2023-y-siguientes/revision.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2023-y-siguientes/casillas/c01__c05.toml:1`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_187_188_194_registry.py:120`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_188_resumen_matches_its_design.py:1`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:131`
- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-188-design-era-coverage-reference.md:1`
- `.vault/audit/2026-08-25-registry-temporal-coverage-s46-m188-design-era-review-audit.md:1`
- `2026-08-22-source-casilla-integration-adr`
