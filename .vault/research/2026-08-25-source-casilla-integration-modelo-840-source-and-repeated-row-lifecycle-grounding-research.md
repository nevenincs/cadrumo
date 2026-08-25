---
tags:
  - '#research'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:e8e3a22eaa08ad7f5319d09de7305fdcb5cdfae9a1275d105578e7bd5a47b803'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - '[[2026-08-25-source-casilla-integration-modelo-840-source-and-repeated-row-owner-deferral-adr]]'
---
# `source-casilla-integration` research: `modelo 840 source and repeated row lifecycle grounding`

This research establishes the factual boundary for Modelo 840's single
`2003-y-siguientes` revision and `0A` cadence.  The official form and record
design prove a declaration surface containing repeatable local facts, while the
current registry, source mesh, and secure observations establish no lossless
source owner for that surface.  It does not decide a disposition; the
model-scoped ADR must settle whether that gap blocks source connection.

## Findings

### The official 2003 artefacts establish both declaration facts and a repeated-local fact family

Orden HAC/2572/2003 approves Modelo 840 and its `RelaciÃ³n de locales` annex
from 19 September 2003.  The enrolled BOE form specification is the published
2003-09-18 version, SHA-256
`1b820ea36307beb67372f1eb648d865d3dd912a1c3bf9d926b8455b551f9c722`.
Its annex prints nine local slots, each with street/address and municipality
coordinates plus distinct `Total`, `Rectificada`, and `Computable` surface
values.  This is therefore a repeated, per-local fact grain; a count, a
summary, a single activity epigraph, or a fixed byte position cannot represent
an individual local or distinguish absent from supplied slots.

The AEAT record design is `dr840.pdf`, published as the 01 December 2003
record design and stored as the 101,013-byte `aeat-dr-840` artefact with
SHA-256 `d0348a78787db7eb767dd8093ea84773c248c0b92bcefb512972573aff34391a`.
Its annex repeats the same address and three-surface group nine times and
carries partial totals.  The design also contains declarant, representative,
event, activity, local, and IAE facts outside that annex.  Those targets prove
the filing vocabulary and record shape, not where Cadrumo can acquire or own
the facts.

### The enrolled registry intentionally stops before the repeated-local lifecycle

The current `840/2003-y-siguientes/0A` snapshot is applicability-grade and
contains 121 informational casillas, no binding, formula, or export-layout
declarations, and a two-target declaration-PDF extraction profile.  Its review
record explicitly rejects converting the repeated annex into more fixed
casillas: the required eventual shape is a row binding and a layout after a
binding set exists.  The authenticated AEAT read surface is separately marked
read-only.  Thus the registry documents targets and restricted post-filing
observation, but no M840 source fact, row carrier, selected destination map,
or pre-filing manual lifecycle.

`FilingProducerKey` and the generic producer namespace retain M840 labels so
that vocabulary can be transcribed without pretending to own values.  Exact
caller searches find no M840 producer values, source-mesh resolver, row
binding, or source-connectivity census disposition.  The profile's repeatable
`activities.iae_epigraph` carrier is only an activity classification and does
not establish the full repeated-local identity, address, surface, absence, or
provenance semantics.

### Existing encrypted threshold evidence is a narrow observation, not a model-wide owner

The encrypted annual continuity tests persist an IAE INCN-exemption assessment
and two declaration-context header observations through `app_filing` custody.
That proves the named threshold assessment can survive its own secure
observation route; it neither captures the complete declaration facts nor
preserves one local row's identity, address, three surface values, absence
state, and source provenance.  It cannot establish a non-lossy pre-filing owner
for either the declaration family or the annex family.

### CRLF and post-filing artefacts are transport or read evidence, not a source fact

Each official fixed record terminates in CRLF, and the current renderer's
terminator bridge is governed by the distinct generic export work.  It creates
neither a local row source nor an M840-specific writer.  Likewise, a PDF
coordinate, record-layout byte span, producer key, authenticated read, or
already-filed declaration can validate presentation or observe a historical
filing only after facts exist; none supplies acquisition, native grain,
absence semantics, secure ownership, or replayable provenance for a new value.

The remaining ADR question is limited to the two genuine source families:
whole declaration/activity facts and individual `RelaciÃ³n de locales` rows.
A future source programme would need to identify authoritative carriers and
durable identities, preserve exact value/absence semantics, map only approved
semantics to registry destinations, and prove the encrypted source lifecycle.

## Sources

- https://www.boe.es/buscar/act.php?id=BOE-A-2003-17642
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G323.shtml
- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/resto-modelos.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_Resto_Mod/archivos/dr840.pdf
- `src/cadrumo/_data/registry/aeat/legal/iae.toml:122`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_840/manifest.json:1`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_840/files/01-840-orden-hac-2572-2003-99-kb-pdf.pdf.extracted.md:266`
- `src/cadrumo/_data/corpus/aeat_official/forms/modelo_840/files/01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf.extracted.md:247`
- `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/revision.toml:1`
- `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/extraction_profiles/0001-extraction-profiles.toml:1`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_840_registry.py:46`
- `src/cadrumo/application/calculations/tests/test_modelo_840_iae_continuity.py:85`
- `src/cadrumo/application/filing/_export_producer.py:84`
- `.vault/reference/2026-08-24-registry-completeness-closure-modelo-840-record-terminator-and-design-extent-reference.md:1`
- `2026-08-22-source-casilla-integration-adr`
