---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:b6357d4e505b32c2ef100e15e064f3516c70679c4245be321a3706778231c007'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` reference: `Modelo 185 historical design and filing boundary`

## Summary

Modelo 185 revision `2003-2025` has a precise, primary-source historical
record design: BOE-A-2003-1911, Orden HAC/96/2003, Annex I. It is not presently
fileable in Cadrumo because the six official Annex-I field-table images have
not been acquired and hash-pinned in the record-design corpus, and the
revision therefore has no historical semantic map, complete casilla/producer
surface, generated export, or filing-grade review. This is an authorable
acquisition-and-export gap, not a terminal no-authority refusal. The 2026 AEAT
PDF is a separate 500-position design and cannot be copied back to the
120-position historical window.

## Exact historical authority and period boundary

BOE-A-2003-1911 was published on 30 January 2003. Its final provision makes
it applicable to monthly declarations for January 2003 and later. Its first
provision approves the Modelo 185 physical and logical designs in Annex I, and
Annex I fixes two logical record types at 120 positions. The BOE record's
analysis lists the later 2026 derogation and a related Modelo 156 instrument,
but no modifying Modelo 185 design instrument.

BOE-A-2025-21726 expressly says that Orden HAC/96/2003 continues to apply to
presentations for periods before the entry into force and applicability of the
new order. Its derogation applies to monthly declarations for exercise 2026
and later. This proves the registry's legal split at 31 December 2025 / 1
January 2026. It does not permit one era's bytes to stand in for the other.

The official BOE HTML exposes the exact historical field tables as Annex-I
images. They were re-fetched on 2026-08-24 from the official BOE endpoints and
have these SHA-256 values:

- `01911_8166990_image1.png`: `20161e4c4398f83a26e4aa1423b17f6315b3affc1a13853bb78d5156ec768a4a`
- `01911_8166990_image2.png`: `02c30521cb182866a4fd2ebd870ce1d3a26e35c410d48c89edde8485ce248cc9`
- `01911_8166990_image3.png`: `3c23bdcdb5a79b290fec3ab0d797cc9fe53d02d8677437efc20e2164ca237eb5`
- `01911_8166990_image4.png`: `844506665759c94ea048b9f22accaa3dd3ead7f4dd0a45f206955b60adbe6e19`
- `01911_8166990_image5.png`: `e6244568223f24553b32f9644861ebf16cf29d784da3900bce9f8c9e8efa68fa`
- `01911_8166990_image6.png`: `9be6b562cd0359ac4fa3fab09585f86da25c605c2d96538246f91c04d9199338`

The type-1 design fixes positions 1, 2--4, 5--13, 14--53, 54--57, 58--59,
60--69 and 70--120 respectively as record type, modelo, declarant NIF, legal
name, exercise, month, declared-record count and blanks. Type 2 fixes the
same opening identifiers, then declared NIF, name, affiliation number,
identification, pluriactivity, monthly situation/cotisation/day/jornada fields,
the two preceding-month sets, and blanks through position 120. The official
images also carry the encoding and zero/blank alignment rules. This is enough
to acquire a source and build an exact historical parser/map; it is not a
licence to invent an implementation before the source is enrolled.

## Current shipped boundary

The validated registry keeps `2003-2025` at `authority_grade =
"applicability"`; it has only two declaration-header casillas and no export
layout. It cites the BOE order as procedural/layout approval but does not cite
a `record_design` source for its own period. The source catalogue currently
contains only `aeat-dr-185-2026`, whose scope begins on 1 January 2026.

The live filing-capability worklist therefore correctly reports Modelo 185
`2003-2025` as blocked on era and having no export layout. The current
2026-onward generated tree is separately registered against
`aeat-dr-185-2026`; its type-1 layout uses 500 positions and places the
exercise at positions 5--8. That materially differs from the historical
type-1 120-position record, where the exercise is at positions 54--57. The
current design cannot substantiate a historical export, and a historical
layout must not change the existing 2026 source or its generated-tree proof.

## Adjudication, owner, and reconsideration

**Disposition: retain the historical revision as applicability-only and
non-fileable.** There is no authority for claiming a shipped 2003--2025 export
until the official Annex-I design is made a first-class, hash-pinned
record-design source and the full output path exists. The disposition is
specifically not a denial that a source exists: BOE-A-2003-1911 is the exact
legal design authority and its Annex-I field images are retrievable primary
material.

The existing export owner, `2026-08-10-aeat-export-fragment-generator-authority-plan`,
must receive the acquisition, source-registration, semantic-map, generated-tree,
and emitted-byte work in closure-plan step `W02.P04.S28`. No temporal change is
owned here: the 2003--2025/2026 boundary is already law-determined. A later
source owner is required only if the authoring work finds the historical
type-1/type-2 values lack a live, provenance-carrying producer; S16 does not
pretend that those runtime values are already available.

Reconsider historic fileability only after all of the following are separately
landed and reviewed:

1. Archive the BOE original PDF or all six Annex-I images in the official
   corpus; register immutable hashes, retrieval details, and the exact
   2003-01-31 through 2025-12-31 source scope.
2. Parse and independently check the historical 120-position type-1/type-2
   field tables, including the values and conditional fields that differ from
   the 2026 design; split again if newly acquired primary evidence establishes
   an intervening amendment.
3. Declare every historical field's casilla or namespaced producer owner,
   provide any necessary typed source lifecycle and provenance, and prove no
   current 2026 coordinate is reused.
4. Build the reviewed semantic map, render profile, generated fragments, and
   production emitted-byte proof at the historical official offsets.
5. Promote the selected revision only when the complete evidence supports the
   filing-grade claim. This adjudication authorizes neither remote submission
   nor a compatibility layout.

## Sources

- BOE-A-2003-1911, Orden HAC/96/2003, original text, Annex I and official PDF,
  retrieved 2026-08-24: https://www.boe.es/buscar/doc.php?id=BOE-A-2003-1911
- BOE-A-2003-1911, official original BOE pages 3911--3920, retrieved
  2026-08-24: https://www.boe.es/boe/dias/2003/01/30/pdfs/A03911-03920.pdf
- BOE Annex-I field-table images, retrieved 2026-08-24:
  https://www.boe.es/datos/imagenes/disp/2003/26/01911_8166990_image1.png
  through
  https://www.boe.es/datos/imagenes/disp/2003/26/01911_8166990_image6.png
- BOE-A-2025-21726, Orden HAC/1197/2025, preamble, derogation and final
  provisions, retrieved 2026-08-24:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2025-21726
- AEAT Modelo 185 record-design catalogue, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- `src/cadrumo/_data/registry/aeat/legal/modelo-185.toml`
- `src/cadrumo/_data/registry/aeat/modelos/185/revisions/2003-2025/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_185/`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `dev/registry/tests/test_generated_export_trees.py`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`
