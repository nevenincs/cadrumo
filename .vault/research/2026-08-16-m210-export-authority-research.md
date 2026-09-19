---
tags:
  - '#research'
  - '#m210-export-authority'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:09f384d4692b53ef3adcd86fe4b28afe1d7bdf5c735850eb696a8259c51f1097'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-07-10-m210-irnr-phase-2-engine-adr]]"
  - "[[2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr]]"
---

# `m210-export-authority` research: `IRNR party-identity producer key family for the Modelo 210 export layout`

Modelo 210 has no export layout, and the question is what actually blocks one. The
answer is not transcription. The shipped parser already reads the bundled official
design completely, and every printed casilla number on it already has an authored
casilla. What has no canonical typed owner is the form's party and address surface:
roughly half its anchors describe *who* is filing, *for whom*, *through whom*, and
*about which property*, and the closed producer-key enum the export boundary resolves
against carries no IRNR party vocabulary at all. This document records the measured
anchor census, the two distinct address shapes the form uses, and the option space for
supplying them.

## Findings

### The bundled design parses completely and is the smallest generator target enrolled so far

`extract_record_design` returns a complete extraction for the bundled Modelo 210
design binary, with no partial-read fallback required. The 2022 edition
(`aeat-dr-210-2022`, `corpus/aeat_official/disenos_registro/modelo_210/files/02-210-devengos-entre-01-06-2022-y-01-01-2026.xls`)
yields two fixed records, `Página 01` with 127 fields over 2700 declared positions and
`Página 02` with 40 fields over 1400, for 167 anchors total. The 2026 edition
(`aeat-dr-210-2026`) yields the same 127/40 record shape.

Neither record declares a variable envelope or an auxiliary envelope header. That is
materially simpler than every design currently enrolled in the generator: Modelo 303
spans 426 anchors across six records with a DP30300 prefix, and Modelo 390 spans 550 to
634 anchors with a separately governed 13-anchor auxiliary header. Modelo 210 needs
neither mechanism, so nothing in its generation depends on the composite-closing or
auxiliary-header contracts.

### Every printed casilla number on the design already has an authored casilla

The design carries its printed casilla numbers inline in the Contenido text as bracketed
tokens, `[4]` through `[31]`. Twenty-eight anchors carry such a token. Revision
`210/2025` authors 34 casillas, of which 28 declare a numeric `number` field, and the two
sets correspond exactly: `[4]` to `base_imponible_directa_i`, `[5]` to
`rendimientos_integros`, `[8]` to `base_imponible`, `[17]` to
`base_imponible_ganancias_h`, `[22]` to `cuota_integra`, `[31]` to `cuota_diferencial`,
and so on across the Determinación de la base imponible and Liquidación blocks.

The join is therefore already available by printed number and needs no new casilla
authoring. The six remaining authored casillas (`tipo_renta`, `valor_catastral`,
`coeficiente_imputacion_inmobiliaria`, `dias_imputacion`, `valor_adquisicion`,
`valor_comprobado_administracion`) are calculation inputs; only `tipo_renta` has a design
anchor, and the rest legitimately do not appear on the fixed-width record.

### The unowned surface is party identity, and it is about half the form

Partitioning all 167 anchors by the block prefix AEAT uses in its own Contenido text
gives: liquidación 36, envelope and other 27, representante 22, reservado para la
Administración 18, contribuyente 18, situación del inmueble 16, ingreso 11, declarante 8,
devengo 4, pagador 3, renta obtenida 2, autoliquidación complementaria 2.

Of these, the 18 reservado anchors are filler, the 27 envelope anchors are literals and
the fin-de-registro marker, the 36 liquidación anchors are casillas or small
liquidación-local facts, the 11 ingreso anchors on `Página 02` are payment and account
data, and the 4 devengo anchors are draft attributes. That leaves roughly 84 anchors
across declarante, contribuyente, representante, pagador and inmueble with no canonical
typed owner.

### The closed producer-key enum has no IRNR party vocabulary

`src/cadrumo/core/_filing_producer_key.py` declares the closed set of non-derived values
the export boundary may supply. It is organised as generic cross-modelo identities
(`taxpayer.*`, `presenter.*`, `contact_person.*`, `selected_account.*`,
`amendment_evidence.*`) plus per-modelo fact families (`m303.*`, `m111.*`). Every member
is a flat dotted scalar; there is no structured or parameterised member, and the one
address-shaped member, `selected_account.bank_address`, is a single free-text scalar.

Nothing in the enum expresses the party structure Modelo 210 requires. In particular
`taxpayer.*` conflates two parties the form deliberately separates.

### Modelo 210 separates the filer from the taxpayer, with an explicit capacity flag

Anchors 7 and 8 name the *Persona que realiza la autoliquidación* by NIF and by
name, and anchors 9 to 14 are six mutually exclusive one-character capacity flags for
that person: Contribuyente, Representante, Pagador, Depositario, Gestor, Retenedor.
Anchors 21 to 38 then name the *Contribuyente* separately, and anchors 39 to 61 the
*Representante del contribuyente*.

So the filer is not the taxpayer in the general case, and the form records in which
capacity the filer acts. `presenter.tax_id` is the nearest existing key but carries no
capacity axis, and `taxpayer.tax_id` cannot serve both roles without collapsing a
distinction the official design encodes in six dedicated positions.

### The form uses two different address shapes, and they are not substitutable

The *Representante del contribuyente* domicilio (anchors 43 to 58) and the *Situación del
inmueble* (anchors 65 to 80) share an identical fifteen-component Spanish-coded address
vocabulary in the same order: Tipo de Vía, Nombre de la Vía Pública, Tipo de numeración,
Número de casa, Calificador del número, Bloque, Portal, Escalera, Planta, Puerta, Datos
complementarios, Localidad, Código Postal, Código INE del Municipio, Código Provincia.
The inmueble block adds Referencia catastral (anchor 81); the representante block adds
fixed phone, mobile and fax (anchors 59 to 61).

The *Contribuyente* residence block (anchors 29 to 38) is a different shape: Domicilio,
Datos complementarios, Población/Ciudad, Correo electrónico, Código Postal (ZIP),
Provincia/Región/Estado, Código País, Teléfono fijo, Teléfono móvil, FAX. It is a foreign
address in free text, with a ZIP rather than a five-digit código postal, a
province/region/state name rather than a two-digit código provincia, no INE municipal
code, and no vía decomposition.

This matters for reuse: the Spanish-coded shape carries constraints (numeric INE code,
two-digit province code, five-digit postal code) the foreign shape does not, so the
foreign block is not promotable to the Spanish one, and a single shared address family
covering both would have to drop exactly the constraints that make the Spanish one
checkable.

### An identical Spanish-coded component vocabulary already exists, but in an adapter

`CensalDomicilio` at `src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:240`
models an AEAT address group with `tipo_via`, `nombre_via`, `tipo_numero`,
`numero_casa`, `calificacion_numero`, `bloque`, `portal`, `escalera`, `planta`,
`puerta`, `complemento`, `localidad`, `referencia_catastral`, `codigo_postal`,
`municipio` and `provincia`. That is component-for-component the Spanish-coded shape
Modelo 210 uses, which is unsurprising: both are AEAT surfaces describing the same
official address grammar.

It is, however, an outbound-adapter model describing a scraped consulta payload, not a
core value type. A producer key family cannot resolve against it without inverting the
architectural direction, and duplicating the vocabulary per party would create the
parallel definitions the naming and architecture rules exist to prevent. Where the
canonical component vocabulary should live is therefore an open question this research
does not settle.

### Generation is blocked behind two further authored artefacts, not just the enum

The export tree is generated, never hand-authored: `render_complete_export_tree` in
`dev/registry/_export_tree.py` consumes a hash-verified design intermediate joined to a
persisted semantic map and a source-bound render profile, and writes a
`_generation.provenance.json` beside the fragments. Modelo 303 is the only modelo with a
committed `export/` tree today.

So a Modelo 210 layout needs a semantic map under `dev/registry/mappings/modelo_210/`
bijecting all 167 anchors to canonical owners, and a render profile under
`dev/registry/render_profiles/modelo_210/`. The semantic map cannot be authored before
the owners exist, because `SemanticMapEntry` requires exactly one typed payload per
entry and validates producer keys against the closed enum.

### The design binaries were unreachable until the epoch declaration landed

`resolve_record_design_binary` refuses any `record_design` source that declares no
`record_design_epoch`. All three Modelo 210 design sources lacked one, as did 60 of the
catalogue's 121 record-design sources. Epochs have since been declared on 40 of them
across 18 modelos, and `load_record_design_intermediate` now resolves
`aeat-dr-210-2022` at filing year 2025 and `aeat-dr-210-2026` at 2026. This is recorded
here only as the precondition that is now satisfied; it is not part of the option space
below.

### What was not investigated

The `Página 02` ingreso block (11 anchors) was censused but not mapped against
`selected_account.*` member by member, so whether that block needs any new key beyond the
existing account family is unresolved. The 2026 edition was confirmed to have the same
record and field counts as 2022 but its anchor semantics were not diffed, so whether one
reviewed map can be re-keyed across both epochs or each needs independent hand review is
open. Modelo 210's relationship to Modelo 211 (anchor 103 records a Modelo 211
justificante number) was not explored.

## Sources

- `src/cadrumo/core/_filing_producer_key.py`
- `src/cadrumo/core/_record_design_epoch.py`
- `src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py:240`
- `dev/registry/_export_tree.py`
- `dev/registry/_record_design_ir.py`
- `dev/registry/_semantic_map.py`
- `src/cadrumo/domain/calculations/registry/_corpus_catalogue.py`
- `src/cadrumo/_data/registry/aeat/legal/irnr.toml`
- `src/cadrumo/_data/registry/aeat/modelos/210/revisions/2025/casillas/`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_210/files/02-210-devengos-entre-01-06-2022-y-01-01-2026.xls`
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_22/dr210e22.xls
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_26/dr210_2026.xlsx

Anchor counts, block partition and component vocabularies above were measured directly
from the bundled binary through the shipped parser, not read from a derivative extract.
