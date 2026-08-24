---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:46dd9bbeb4cafbbc3c6753d38240a6e8b05dd2eea25806dbeafc6fb6e2de742c'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` reference: `Modelo 840 record terminator and official design extent`

## Summary

Modelo 840 revision `2003-y-siguientes` remains applicability grade and
non-fileable. Its official record-design source is real, complete, and still
published by AEAT, but producing a filing requires the existing export campaign
to bridge one precise, generic source-to-transport distinction. No Modelo
840-specific encoder, terminator literal, or parallel schema may be introduced.

## Official extent and the exact terminal geometry

AEAT's current “Resto de modelos” catalogue lists one Modelo 840 design,
“840 - Orden HAC/2572/2003” (PDF). Its historic-resto catalogue lists no
separate Modelo 840 design. The bundled artifact is hash-verified as
`d0348a78787db7eb767dd8093ea84773c248c0b92bcefb512972573aff34391a` and
the current registry source `aeat-dr-840` names it as the 2003 record-design
authority.

`extract_record_design` reads all three fixed records without loss:

- Page 1: 106 source rows, total 1,132 bytes; ten-byte closing identifier
  `</T840010>` at positions 1,121--1,130; two-byte CRLF row at 1,131--1,132.
- Page 2: 110 source rows, total 1,165 bytes; ten-byte closing identifier
  `</T840020>` at positions 1,154--1,163; two-byte CRLF row at 1,164--1,165.
- Annex: 165 source rows, total 1,067 bytes; ten-byte closing identifier
  `</T840030>` at positions 1,056--1,065; two-byte CRLF row at 1,066--1,067.

Each final source row is explicitly labelled `Salto de línea. Constante CRLF.`;
it is not a blank filler and not part of the preceding closing identifier. The
source date printed in the PDF is 1 December 2003. BOE-A-2003-17642 entered
into force on 19 September 2003 and its current consolidated page reports no
subsequent update. Together with the single current AEAT catalogue entry and
the absence of a historic alternative, that is the published evidence for the
one enrolled 2003 design. It does not prove a second, invented design era.

## Canonical-contract finding

The canonical fixed-width codec already owns wire termination. Its body renderer
ends at the last ordinary field; `render_fixed_width_export_record_payload`
then appends the record's declared `line_ending`, including `crlf`. The
record-design parser separately preserves an official CRLF source row as a
two-byte field, rather than dropping it. Those authorities must remain
separate: the official source owns the two bytes; the transport profile owns
how those two bytes are appended to emitted records.

The missing bridge is in the development generator's exact semantic-map join.
It currently requires every fixed parser field to have exactly one
`SemanticMapEntry`, while the entry-kind vocabulary has no transport-terminator
meaning. Mapping a CRLF row as a literal tries to write the four-character
source name `CRLF` into a two-byte slot. Mapping it as filler writes spaces.
Leaving it unmapped correctly fails the bijection; mapping it as an ordinary
field and also declaring `line_ending = "crlf"` would double the terminator.

Thus the former worklist wording is only partly right: a generic mapping
contract is absent, but the canonical renderer is not unable to emit CRLF. The
repair must teach the existing generator to retain the official terminal-row
anchor as evidence while emitting it once through the existing transport
contract. It must preserve exact source coverage, exact declared record totals,
and a mutation proof for omission, replacement by spaces, and doubled CRLF.

## Shipped boundary and owners

**Disposition: retain Modelo 840 at applicability grade with no export layout
and no filing capability.** The lack of a layout remains visible. The official
design alone does not supply the declaration-wide identity, activity,
representative, and repeating local-row values, nor does it establish a product
filing-authority decision.

`W02.P04.S26` owns any change to the law-selected revision horizon or authority
grade. `W02.P04.S27` owns the source and binding lifecycles needed for the
declaration and repeated `Relación de locales` values. `W02.P04.S28` owns the
single generic terminator bridge, the reviewed Modelo 840 semantic map and
render profile, canonical generated fragments, and emitted-byte proof. `S28`
must use the existing fixed-width codec and tree publisher; it must not add an
M840 writer, a second terminator table, or a local submission route. `W02.P04.S29`
will retain the revision on the capability worklist until that owner has closed
the filing proof.

Reconsider filing grade only after the owner has shown: every official source
anchor is represented exactly once or is represented by the reviewed transport
terminator contract; all required values have governed producers, bindings, or
projections; canonical generation yields the three exact record lengths and one
CRLF per record; a real production export has been checked at official offsets;
and an accepted authority decision permits Cadrumo to claim this filing
surface. No empty layout or generic codec result is evidence of filing support.

## Sources

- AEAT, “Resto de modelos”, Modelo 840 record-design entry, retrieved
  2026-08-24: https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/resto-modelos.html
- AEAT, “Ejercicios anteriores: Resto de modelos”, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-resto-modelos.html
- AEAT, Modelo 840 procedure page, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G323.shtml
- BOE-A-2003-17642, Orden HAC/2572/2003, retrieved 2026-08-24:
  https://www.boe.es/buscar/act.php?id=BOE-A-2003-17642
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_840/files/01-840-orden-hac-2572-2003-99-kb-pdf.pdf`
- `src/cadrumo/_data/registry/aeat/legal/iae.toml`
- `src/cadrumo/domain/calculations/registry/_record_design.py`
- `src/cadrumo/domain/calculations/registry/_fixed_width_codec.py`
- `dev/registry/pipeline/_semantic_map.py`
- `dev/registry/pipeline/_semantic_map_validation.py`
- `dev/registry/pipeline/_export_tree.py`
