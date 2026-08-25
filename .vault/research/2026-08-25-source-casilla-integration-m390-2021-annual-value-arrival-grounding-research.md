---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:721c612191b2ed7fa06b509ec8f3f504573b1c314886e846fa38de5b40045c67'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-25-source-casilla-integration-m390-2021-source-owner-deferral-adr]]'
---

# `source-casilla-integration` research: `m390 2021 annual value arrival grounding`

This research establishes the factual boundary for Modelo 390's exact 2021 annual
return surface: the official design establishes a complete, heterogeneous annual
record, whereas the enrolled 2021 registry is a deliberately sparse parser of an
already-filed declaration. It records no source-owner conclusion. The model-scoped
ADR must decide the disposition and reopening condition from these findings.

## Findings

### The official 2021 contract is a complete annual record, not ten IVA totals

The enrolled primary AEAT record design is the 25 November 2021 edition
`dr390e2021.xlsx`, with SHA-256
`0164fbea6f500a63950b762f5b5e43c5d771f84ac8d260e70dc1497acaed4246`,
497,063 bytes, and a closed 2021-01-01 through 2021-12-31 applicability
window. Its envelope fixes `390`, the annual `0A` period, and the exercise; page
one requires taxpayer identity and carries group, cash-accounting, insolvency,
amendment, activity/IAE, joint-declaration, and representative facts. The BOE
form record describes Modelo 390 as the annual IVA declaration-summary and notes
that Orden HAC/646/2021 applies its revised form first to exercise 2021.

The record's remaining pages establish distinct fact grains that cannot be
represented as a single annual aggregate: general-regime bases and cuotas by
rate, group, cash-accounting, used-goods, travel, intra-Community, reverse-charge
and adjustment branches; deductible amounts by transaction class and
investment/current-good distinction; simplified-regime activity and module rows;
annual settlement and territorial allocation; annual periodic-result history;
operation-volume categories; specific operations; up to five prorrata activity
rows; and three differentiated-deduction sector blocks. A zero, an inapplicable
branch, an absent repeatable row, and a supplied annual value are therefore
separate facts to preserve at their native identity and grain.

### The 2021 registry owns only an observation parser

The law-determined `390/2021/0A` revision is applicability-grade and contains
ten informational casillas: boxes 02, 04, 06, 26, 49, 47, 64, 65, 97 and 662.
Its only application link is an extractor consuming a declaration PDF. The
loaded snapshot has no bindings, formulas, export layouts, deadline windows, or
filing application link. Its own review stamp confines the claim to exact parser
casillas and expressly says that filing-layout authority is not claimed.

The extraction profile does not change that boundary. It reads values from an
already-filed declaration, allows legitimate blank leaf rate boxes, and observes
the printed but blank 662 box without fabricating an amount. Those parser
semantics cover only the declared observations; they do not state the origin,
identity, aggregation, source capture, or absence semantics of the official
record's remaining facts. The independent M390 parser audit confirms the
extractor-only lifecycle and the intentional absence of a filing consumer.

### Existing later-year routes and filed declarations are not a 2021 value owner

The current annual-compensation resolver acts only when the selected annual
revision declares its partition requirement, then reconstructs its two outputs
from persisted filed Modelo 303 observations. The current investment-goods
resolver likewise locates a declared binding before it can project the
register-backed amount to its M390 output. Since the 2021 revision declares no
bindings, neither route establishes a 2021 source connection; even their later
targets cover only narrow parts of the official 2021 surface.

A real encrypted owner exists for an already-filed declaration and its parsed
observations. It is deliberately read-only historical evidence: it supports
reconciliation or a future declared previous-filing binding, but cannot be a
pre-filing economic source or recover fields it does not observe. The filing-grade
2022 revision separately supplies manual bindings and export producer keys
against the 2022 design. These later routes are not evidence that 2021 has the
same facts, capture, owner, or lossless period boundary. The registry itself
states that 2021 parser observations and 2022 bound filing casillas have distinct
product roles and are not substitution-compatible.

### A filing layout or a parsed declaration cannot settle source provenance

The filing-capability worklist measures the 2021 revision as ten declared
casillas against filing-grade M390 siblings with at least 325. It further
requires a grounded filing-authority judgement as well as a layout. That
separate omission is relevant to a future filing effort, but it neither names
the sources of 2021 values nor permits an export position, producer key, or PDF
coordinate to serve as one. Conversely, a parsed filed declaration is a
post-filing observation and cannot prove a pre-filing non-lossy owner for fields
that it does not observe.

The remaining question for the ADR is consequently narrow: whether a future,
field-by-field 2021 source programme can preserve the official annual facts and
their absence semantics through the existing encrypted calculation-revision
lifecycle, without treating the 2022+ implementation or the parser as an
undocumented substitute.

## Sources

- `src/cadrumo/_data/registry/aeat/legal/iva.toml:628`
- `src/cadrumo/_data/registry/aeat/legal/iva.toml:2806`
- https://www.boe.es/buscar/act.php?id=BOE-A-2009-18472
- https://www.boe.es/buscar/doc.php?id=BOE-A-2021-10509
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_300_399/archivos_21/dr390e2021.xlsx
- `src/cadrumo/_data/corpus/normatives/html/orden-eha-3111-2009.html:781`
- `src/cadrumo/_data/corpus/normatives/html/orden-eha-3111-2009.html:1046`
- `src/cadrumo/_data/corpus/normatives/html/orden-eha-3111-2009.html:1145`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md:1`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md:36`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md:124`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md:332`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md:441`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md:504`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/13-390-ejercicio-2021-actualizado-25-11-2021-486-kb-xlsx.xlsx.extracted.md:566`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2021/revision.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2021/casillas/civa.anual.repercutido.super-reducido__civa.anual.compensacion-generada-ejercicio-no-97.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2021/extraction_profiles/0001-extraction-profiles.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2021/application_links/0001-application-links.toml:1`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_390_rate_box_total_invariant.py:115`
- `.vault/audit/2026-08-22-issue-604-m390-real-parse-implementation-review-audit.md:85`
- `src/cadrumo/application/calculations/_iva_compensation_annual_partition.py:96`
- `src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py:120`
- `src/cadrumo/adapters/outbound/aeat/sede/_schema.py:417`
- `src/cadrumo/adapters/outbound/aeat/sede/_observation_store.py:198`
- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_observations.py:456`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/revision.toml:48`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/bindings/0012-page-01-declared.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/export_layouts/0013-export-layouts-page-01-identity.toml:1`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:595`
