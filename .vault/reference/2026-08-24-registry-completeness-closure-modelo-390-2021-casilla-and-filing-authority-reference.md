---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d1e39e9fde58ba5f7cf1afa2a14a0df296a6cdb82064cbcf76cb1bb980324f03'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `Modelo 390 2021 casilla and filing authority`

## Summary

Modelo 390 revision `2021` remains an applicability-grade declaration-parser
revision. It is law-selected only for filing year 2021 and Cadrumo must not
emit a 2021 filing. This is not a missing official-layout case: the exact AEAT
2021 record design is bundled, hash-pinned, and scoped to the exact annual
window. The decisive gap is the shipped casilla and producer surface.

The revision declares ten informational casillas for extraction from an already
filed declaration. It has no formulas, bindings, filing application link, or
export layout. Each filing-grade Modelo 390 sibling declares at least 325
casillas. An export over the parser's ten observations would therefore produce
a structurally incomplete return while appearing byte-shaped, which is an
unsafe filing claim rather than a permissible reduced capability.

## Official authority and annual scope

AEAT's historic 300--399 design catalogue still lists `390 - Ejercicio 2021
(actualizado 25/11/2021)` as a declaration-resumen-anual IVA record design.
The enrolled `aeat-dr-390-2021` source preserves the retrieved 497,063-byte
workbook at SHA-256
`0164fbea6f500a63950b762f5b5e43c5d771f84ac8d260e70dc1497acaed4246`, marks
it as `layout_authority`, and constrains it to 2021-01-01 through 2021-12-31.
Its extracted field table has the auxiliary page zero plus pages one through
eight, with fixed page extents 1,175, 1,211, 1,398, 378, 1,364, 828, 776, and
1,092 positions respectively. This is concrete record-layout authority, not a
summary-form approximation.

BOE-A-2009-18472, Orden EHA/3111/2009, approves Modelo 390 as the annual IVA
summary declaration. AEAT's historic 2021 procedure still exposes both the
ordinary presentation and `PresentaciÃ³n (con fichero)` routes. The published
filing surface confirms that a submission format existed; it neither supplies
the missing Cadrumo semantic owners nor authorizes an incomplete export.

## Shipped boundary and no-redeclaration result

The loaded snapshot selects revision `2021` only for `2021/0A`, retains
`authority_grade = "applicability"`, and gives its sole application link to
`cadrumo.adapters.inbound.declaracion.parse_declaracion`. Its extractor profile
reads the ten observation targets numbered 02, 04, 06, 26, 49, 47, 64, 65, 97,
and the unnumbered compensation target. Every declared casilla is
`input_kind = "informational"`; the tree has no revision bindings, formulas,
or export layouts.

Vaultspec-RAG semantic discovery, followed by exact-symbol confirmation, found
one existing filing path: `ValidatedRegistryAuthority` selects and validates a
snapshot, the registry export-layout boundary admits only filing-grade revisions,
and the canonical generation and emitted-byte proof authority supplies the
production evidence. There is no second Modelo 390 exporter, alternate closure
composer, `m390.` `FilingProducerKey` namespace, or 2021 semantic-map/render
profile to extend. This Step deliberately adds none. The pending Modelo 390
2022--2025 generator rows are useful precedents, not authority to reuse their
layouts for 2021.

**Disposition: retain 2021 at applicability grade, with its parser capability
and no export layout. The supported parsing and obligation boundary is exactly
2021; the fileable boundary is empty.** The capability worklist's casilla-surface
refusal is expected evidence, not a test to weaken.

## Owner and reconsideration

`W02.P04.S27` must enroll the source-and-casilla work in
`2026-08-22-source-casilla-integration-plan`: classify every required 2021
record-design anchor under the existing casilla and typed value-source
authorities, add only genuinely missing lifecycle and provenance owners, and
preserve the parser observations as their own extractor surface. It must not
copy the current 2022--2025 casillas or infer 2021 values from a later layout.

After the complete 2021 value surface exists, `W02.P04.S28` must enroll export
work in `2026-08-10-aeat-export-fragment-generator-authority-plan`: extend the
canonical producer vocabulary only with approved real value arrivals; author a
source-bound reviewed 2021 semantic map and render profile; generate registry
fragments through the existing publisher; and prove real `export_draft` bytes
at the 2021 official offsets. It must reuse the established authority and
proof pipeline, not create a Modelo 390-specific writer.

No temporal remediation is currently required: the revision and its source
already have the exact closed 2021 scope. Filing grade may be reconsidered only
after the full casilla/value-owner surface, approved producers, reviewed
source-bound map and profile, generated fragments, and live emitted-byte proof
all pass together. This adjudication does not authorize grade promotion, a
compatibility layout, remote submission, or any new export pathway.

## Sources

- AEAT historic 300--399 record-design catalogue, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-300-399.html
- AEAT Modelo 390 exercise-2021 historic procedure, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-390-iva-declaracion-resumen-anual_/ejercicio-2021.html
- BOE-A-2009-18472, Orden EHA/3111/2009, retrieved 2026-08-24:
  https://www.boe.es/eli/es/o/2009/11/05/eha3111
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/manifest.json`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md`
- `src/cadrumo/_data/registry/aeat/legal/iva.toml`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2021/`
- `src/cadrumo/application/registry/_filing_export_coverage.py`
- `src/cadrumo/domain/calculations/registry/tests/test_m390_temporal_epochs.py`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `2026-08-22-source-casilla-integration-plan`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`
