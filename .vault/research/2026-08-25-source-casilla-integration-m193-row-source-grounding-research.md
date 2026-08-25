---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:cd1cd64da4653ed3fa33efc13f10e9f2a48ddc08364c87469357d8be9b4ddec7'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` research: `Modelo 193 contributor-expense row source grounding`

This discovery asks whether Modelo 193's contributor-expense rows have a
non-lossy, secure automated owner that can support source enrollment. Official
evidence establishes a genuine, separate type-2 expense record and the
registry correctly exposes direct manual filing casillas. The current automated
candidate, however, is only a worksheet assembler with synthetic identity and
no secure owner, persistence, replay, or live resolver. The evidence therefore
favours retaining the already-bounded `ingress_blocked` evidence state; this
research does not decide a future owner or authorize S105.

## Findings

### Official evidence establishes an expense annex, not an acquisition channel

The AEAT's 2025 fixed-record design labels the relevant type-2 structure as
the perceptor record's `Relación de gastos`, expressly for Article 26.1.a)
Ley 35/2006. It gives a contributor NIF, a legal-representative NIF only where
applicable, contributor name, and annual expense amount their own positions;
it is consequently neither a generic perceptor/withholding row nor an
unstructured summary total. `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/01-193-orden-eha-3377-2011-actualizado-por-orden-hac-1430-2025-de-3-de-diciembre-357-kb-pdf.pdf.extracted.md:1713`

The evidence is reproducibly pinned in the legal source catalogue: the 2024
late edition has SHA-256
`36184283123fec6827bf830a0b7d1b3e84a45937d7d85d9504d807f334caff8e`
and applies to 2024; the 2025 edition has SHA-256
`25ab19076ecc1116c660f8d4b0c47523e6cd271d89869895699c91843f562489`
and applies from 2025. The underlying BOE form specification is separately
pinned as SHA-256
`6a5405402732de445caf7bbb801142f4dd0e7247f79747e2f0cf289b59cfcb6b`.
`src/cadrumo/_data/registry/aeat/legal/irpf.toml:2563`
`src/cadrumo/_data/registry/aeat/legal/irpf.toml:2582`
`src/cadrumo/_data/registry/aeat/legal/irpf.toml:2725`

Those primary sources define what the declarant must report. They do not name
an application source that captures the four values, retains their provenance,
or supplies a secure replayable record to this system.

### Direct manual casillas are valid entry, but not a connected source owner

Both scoped filing revisions declare the contributor fields as
`gasto193_contributor` row bindings, while the current 2025 casillas
`gasto.nif`, `gasto.nombre`, `gasto.nif-representante`, and `gasto.importe`
are required `manual` inputs. This is a legitimate direct filing-entry path;
it must remain distinct from a claim that an upstream contributor observation
has been acquired, authenticated, or persisted. The fixed-width layout also
maps those four casillas to a repeating `modelo-193-gastos` record, so the
existence of an export grammar does not create an upstream source owner.
`src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/bindings/0002-bindings.toml:89`
`src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/casillas/cgasto.nif__cgasto.importe.toml:3`
`src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/export_layouts/0003-modelo-193-gastos.toml:4`

Reclassifying `gasto193_contributor` itself as `manual_input` would erase that
boundary and incorrectly let a direct-entry surface stand in for source
ownership, persistence, provenance, or replay. The evidence does not support
that reclassification.

### The candidate carrier is lossy and has no secure, live route

The worksheet assembler builds `Gasto193Observation` values only from Detalle
cells. It synthesises `source_id` from the worksheet row number and assigns a
filing-year-end transaction date; neither value is carried by the worksheet as
a durable capture identity or event date. The binding helper then aggregates
the values by contributor NIF. `src/cadrumo/application/calculations/_row_set_assembly.py:950`
`src/cadrumo/domain/calculations/registry/_gasto193_bindings.py:48`
`src/cadrumo/domain/calculations/registry/_gasto193_bindings.py:130`

The canonical source mesh deliberately includes
`GASTO193_CONTRIBUTOR` among deferred kinds. The current census makes the same
limited claim: a typed assembler exists, but no durable source repository or
calculation-revision handoff is owned by a live resolver. It assigns
`source-connectivity-campaign` as owner, expires on 2026-12-31, and gives the
bounded follow-up a 2026-11-30 deadline. The focused exact scan found no
Gasto193 observation repository, persistence, revision, or replay reference;
the two binding resolver functions have definitions and re-exports but no
production caller. This is a scoped codebase finding, not a claim about an
external fact source. `src/cadrumo/application/aggregation/_source_mesh.py:302`
`src/cadrumo/_data/source_connectivity/census.toml:301`
`src/cadrumo/_data/source_connectivity/census.toml:326`
`src/cadrumo/domain/calculations/registry/_gasto193_bindings.py:111`

The separate `RetencionObservationRepository` is encrypted and has a live
withholding purpose, but it owns perceptor/withholding observations rather than
the Article-26.1.a contributor-expense record. Reusing it as proof of a gastos
owner would conflate distinct official rows and source kinds.
`src/cadrumo/application/aggregation/_retencion_observations_repository.py:133`
`src/cadrumo/application/aggregation/_retencion_observations_repository.py:301`

### S105 must establish an owner before enrollment

There is a dormant implementation prerequisite in the current helper: its
resolvers select source string `gasto193`, while each live M193 registry
binding declares `gasto193_contributor`. No production caller currently reaches
those resolvers, so this discovery records the mismatch without changing it.
S105 cannot silently treat the helper as an enrolled route; a future slice must
first select a secure non-lossy contributor-row owner, preserve durable
identity/fingerprint plus capture/document provenance, resolve exactly the
declared source kind, and prove encrypted persistence, revision replay,
diagnostics/operator reachability, and repeated-record export across both
scoped revisions. `src/cadrumo/domain/calculations/registry/_gasto193_bindings.py:111`
`src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/bindings/0002-bindings.toml:89`
`src/cadrumo/_data/source_connectivity/census.toml:327`

Connecting now, repurposing the withholding store, and relabelling the source
as manual input were considered and rejected by the evidence above. Selection
of a future secure owner and its exact acquisition contract remains outside
this discovery and belongs to a separately authorized implementation decision.

## Sources

- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_193_2025.pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_193_2024.pdf
- https://www.boe.es/buscar/act.php?id=BOE-A-2011-19396
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI12.shtml
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2563`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2582`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2701`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2725`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/01-193-orden-eha-3377-2011-actualizado-por-orden-hac-1430-2025-de-3-de-diciembre-357-kb-pdf.pdf.extracted.md:1713`
- `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/bindings/0002-bindings.toml:89`
- `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/casillas/cgasto.nif__cgasto.importe.toml:3`
- `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/export_layouts/0003-modelo-193-gastos.toml:4`
- `src/cadrumo/application/calculations/_row_set_assembly.py:950`
- `src/cadrumo/domain/calculations/registry/_gasto193_bindings.py:111`
- `src/cadrumo/application/aggregation/_source_mesh.py:302`
- `src/cadrumo/_data/source_connectivity/census.toml:301`
- `src/cadrumo/application/aggregation/_retencion_observations_repository.py:133`
