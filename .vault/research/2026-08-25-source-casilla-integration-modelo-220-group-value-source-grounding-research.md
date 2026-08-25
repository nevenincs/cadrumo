---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bab516f357a52de130eb2b402c83cbd5285407b3c787994ff0c9e483a21ae1c9'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` research: `modelo 220 group value source grounding`

Modelo 220 has real group-valued facts for the separately selected 2024 and
2025 eras, but the official designs are declaration targets rather than an
acquisition contract. The current tree has no non-lossy secure owner for their
composite group/member grain. Under the accepted source-connectivity ADR, the
evidence therefore supports a deferred candidate and does not support a
producer, binding, casilla linkage, layout, or census promotion.

## Findings

### The official designs establish a composite group/member declaration grain

AEAT's 2024 `DR220e24.xlsx` is 1,559,124 bytes with SHA-256
`a8f398dd42db0b1142d5f2e98bf3a60d79069e31d63af32001373f459fee4f2e`;
the 2025 `DR220e25.xlsx` is 1,662,928 bytes with SHA-256
`69c3a234e96eb4485a31c65209348bbcede0a49a8c143223c952000784f3f2df`.
Both are AEAT layout authority for only their respective calendar years.
`src/cadrumo/_data/registry/aeat/legal/is.toml:1395`
`src/cadrumo/_data/registry/aeat/legal/is.toml:1409`

Both designs name a dominant entity and numbered dependent/cooperative entity
slots, each carrying identity, entry date, ownership/voting data, and the
receipt number of its individual declaration. They also carry individual-base
and total group-value fields. The fact cannot truthfully be reduced to one
header value or one anonymous total: its minimum source grain is group,
representative/dominant identity, member identity, tax period, the member
individual-declaration reference, and the value's distinct group or member
role. `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/04-220-ejercicio-2024.xlsx.extracted.md:152`
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/04-220-ejercicio-2024.xlsx.extracted.md:2777`
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/01-220-ejercicio-2025.xlsx.extracted.md:152`
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/01-220-ejercicio-2025.xlsx.extracted.md:2744`

### Modelo 200 evidence explains a tax relationship, not an owned source route

The 2024 manual requires every group entity, including the dominant entity, to
file its individual Modelo 200; the 2025 manual explains that the group base
uses the member individual bases with the statutory consolidation rules. It
also keeps some group-only items exclusively in Modelo 220. Those statements
make an individual Modelo 200 a possible contributor to particular group
values, but do not identify the source of membership, consolidation adjustments,
member receipt/provenance, a group calculation version, or an explicit absent
value. `src/cadrumo/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf.extracted.md:1371`
`src/cadrumo/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf.extracted.md:22406`
`src/cadrumo/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2025.pdf.extracted.md:34017`

The BOE records scope the Modelo 220 filing eras, not value origin. The 2025
excerpt expressly identifies the Modelo 220 filing deadline and applies only to
2025; its own provenance note records that the complete approval article is not
bundled. Neither that record nor the 2024 BOE form excerpt proves an application
source, resolver, aggregation policy, capture provenance, or absence semantics.
`src/cadrumo/_data/corpus/normatives/html/orden-hac-529-2026.html:13`
`src/cadrumo/_data/corpus/normatives/html/orden-hac-529-2026.html:19`

### No current source owner can preserve the required fact without loss

Exact repository search found no `m220.` `FilingProducerKey`, M220
`BindingSourceKind`, M220 binding directory, source-mesh resolver, or
source-connectivity census row. The filing worklist independently records that
the absent M220 producer namespace means non-casilla fields have no canonical
identity or application producer. `src/cadrumo/core/_filing_producer_key.py:10`
`src/cadrumo/core/aggregation.py:233`
`src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:573`

The nearby Modelo 222 profile owns fiscal-group identity for a different
quarterly return only. It does not retain the M220 member rows, individual
filing receipt references, group adjustments, value lineage, or an absence
state, so it cannot be reused as a M220 value owner.
`src/cadrumo/application/filing/_producer_snapshot.py:183`

The existing 2024 M220 manual casillas are valid direct filing entry. The 2025
revision remains applicability-only. Neither direct input nor an official
layout coordinate proves encrypted source persistence, immutable source
identity/fingerprint, replay, review, or source-owned export. The accepted ADR
requires these properties before a candidate becomes implementation-ready.
`src/cadrumo/_data/registry/aeat/modelos/220/revisions/2024/casillas/centidades-grupo-dominante.nif__centidades-grupo-dependiente.opcion-fraccionamiento.toml:1`
`src/cadrumo/_data/registry/aeat/modelos/220/revisions/2025/casillas/cdecl.ejercicio__cdecl.tipo-declaracion.toml:1`
`.vault/adr/2026-08-22-source-casilla-integration-adr.md:52`

### A future connection needs a composite secure owner and two-era proof

Connecting from record offsets, from manual casillas, or from Modelo 200
calculation support is rejected: each would infer an origin that the evidence
does not establish. A future owner must securely persist the group and member
identity, period and revision, native value role and units, the relevant
individual declaration/source reference, source fingerprint and capture
provenance, and an explicit distinction between absent, inapplicable, and zero.
It must then prove resolver enrollment, diagnostics/provenance, encrypted
revision persistence and replay, operator/review reachability, and supported
export separately for 2024 and 2025. The 2024/2025 design re-layout precludes
assuming that one era's destination or semantics applies to the other.
`src/cadrumo/_data/registry/aeat/modelos/220/revisions/2025/revision.toml:1`
`.vault/adr/2026-08-22-source-casilla-integration-adr.md:81`

## Sources

- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_24/DR220e24.xlsx
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_25/DR220e25.xlsx
- https://www.boe.es/buscar/doc.php?id=BOE-A-2025-12818
- https://www.boe.es/buscar/doc.php?id=BOE-A-2026-11583
- `src/cadrumo/_data/registry/aeat/legal/is.toml:1395`
- `src/cadrumo/_data/registry/aeat/legal/is.toml:1409`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/04-220-ejercicio-2024.xlsx.extracted.md:152`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/04-220-ejercicio-2024.xlsx.extracted.md:2777`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/01-220-ejercicio-2025.xlsx.extracted.md:152`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_220/files/01-220-ejercicio-2025.xlsx.extracted.md:2744`
- `src/cadrumo/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf.extracted.md:1371`
- `src/cadrumo/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf.extracted.md:22406`
- `src/cadrumo/_data/corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2025.pdf.extracted.md:34017`
- `src/cadrumo/_data/corpus/normatives/html/orden-hac-529-2026.html:13`
- `src/cadrumo/_data/corpus/normatives/html/orden-hac-529-2026.html:19`
- `src/cadrumo/core/_filing_producer_key.py:10`
- `src/cadrumo/core/aggregation.py:233`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py:573`
- `src/cadrumo/application/filing/_producer_snapshot.py:183`
- `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2024/casillas/centidades-grupo-dominante.nif__centidades-grupo-dependiente.opcion-fraccionamiento.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2025/casillas/cdecl.ejercicio__cdecl.tipo-declaracion.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2025/revision.toml:1`
- `.vault/adr/2026-08-22-source-casilla-integration-adr.md:52`
- `.vault/adr/2026-08-22-source-casilla-integration-adr.md:81`
