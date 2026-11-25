---
tags:
  - '#research'
  - '#informativa-party-name'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:ed3c0aadcc543319622a1d7cf5d3b4d78a0fb13b7fa6c95a335a5917a396ab09'
related: []
---

# `informativa-party-name` research: `Party-name fields in informative-return designs and the registry`

The question: which AEAT informative-return designs carry a third-party name field, what each one says that field must contain, and whether any design allows a party name to be shortened. Every captured design states the same content rule: for natural persons, surnames first in a fixed order; for entities, the complete razón social. The searches found no abbreviation or truncation rule for party names. The registry publishes these fields in at least ten modelos, all not required. The decision is left to `2026-11-11-informativa-party-name-adr`.

## Findings

### The designs prescribe one content rule

Corpus root: `src/cadrumo/_data/corpus/aeat_official/disenos_registro/`. Each file below is `modelo_<n>/files/<file>.extracted.md`. Line numbers are those of the extracted text.

- **347 (2025 y siguientes), declarado.** File `01-347-ejercicio-2025-y-siguientes-modificados-p.pdf`, lines 272-284, positions 36-75 "APELLIDOS Y NOMBRE, RAZÓN SOCIAL O DENOMINACIÓN DEL DECLARADO":
  - a) "Para personas físicas se consignará el primer apellido, un espacio, el segundo apellido, un espacio y el nombre completo, necesariamente en este mismo orden. Si el declarado es menor de 14 años, se consignarán en este campo los apellidos y nombre del menor de edad."
  - b) "Tratándose de personas jurídicas y entidades sin personalidad jurídica, se consignará la razón social o la denominación completa de la entidad, sin anagramas."
  - The arrendatario field of the inmueble record (lines 905-913, positions 36-75) has the same wording.
- **180, perceptor.** File `01-180-orden-hap-1732-2014-actualizado-por-orden.pdf`, lines 254-263, positions 36-75: same a) and b).
- **190, perceptor.** File `01-190-orden-eha-3127-2009-de-10-de-noviembre-ac.pdf`, lines 330-340, positions 36-75: same a). Its b) covers only "entidades en régimen de atribución de rentas ... denominación completa de la entidad, sin anagramas". Files 02-04 (other editions) carry the same text at lines 327-337 and 329-339.
- **193, perceptor.** File `03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf`, lines 390-411, positions 36-75: same a) ("menor de edad"). Its b) reads "personas jurídicas y entidades en régimen de atribución de rentas ... razón social o denominación completa de la entidad, sin anagramas".
- **194, perceptor.** File `01-194-diseno-de-registro-actualizado-en-2024.pdf`, from line 334, positions 36-75: same wording.
- **184, declarado.** File `01-184-ejercicio-2025-y-siguientes-modificados-p.pdf`, lines 1848-1862, positions 36-75: same wording.
- **156, afiliado.** File `01-156-diseno-de-registro-vigente.pdf`, lines 166-169, positions 36-75: natural persons only, same order.
- **349, operador intracomunitario.** File `01-349-orden-hac-174-2020-de-4-de-febrero-ejerci.pdf`, lines 312-316, positions 93-132 (40 positions): "Se cumplimentará con el mismo criterio que el especificado para el declarante en el registro de tipo 1".
  - The declarant criterion it points to is lines 52-58, positions 18-57: "Si es una persona física se consignará el primer apellido, un espacio, el segundo apellido, un espacio y el nombre completo, necesariamente en este orden. Para personas jurídicas y entidades en régimen de atribución de rentas, se consignará la razón social completa, sin anagrama. En ningún caso podrá figurar en este campo un nombre comercial."
- **Declarant and contact-person fields.** The declarant field (positions 18-57) of 190 (file 01, lines 88-98), 194 (file 01, lines 60-69) and 720 (file 01, lines 115-124) uses the same wording, including the nombre comercial exclusion. The contact-person sub-field at 68-107 states the natural-person order in each header.
- **Not read.** The design text of the casilla-kind name fields of 165, 181, 185, 189, 270, 280 and 345, and of the 232 and 390 name bindings, was not read field by field.

### No design allows shortening a party name

Every `*.extracted.md` under the corpus root was searched, case-insensitively:

- **No hits:** "primeros caracteres", "primeras posiciones", "truncar", "truncad", "recortar", "no quepa", "no cabe", "se omitir".
- **"no cupiese":** five files, 180 (01, 03), 347 (01, 04) and 720 (01). Every hit is the vía-pública street-name rule, for example 180 file 01 lines 444-449 at positions 140-189, and 720 file 01 lines 651-658 at positions 251-302: "Se consignará el nombre largo de la vía pública, si no cupiese completo el nombre, no se harán constar los artículos, preposiciones ni conjunciones y se pondrán en abreviatura los títulos (vgr. cd = Conde). Los demás casos se abreviarán utilizando las siglas de uso general."
- **"abreviatura" / "abreviad":** the same street rule (180, 181, 347, 720), the "Mod.abreviado" balance options (200 files), and 303 workbook text.
- **"exceda" / "excediera":** a filtered pass on lines that also mention nombre, razón, apellid or denominación returned only the vía-pública lines.

The only shortening rule in the corpus therefore applies to street names. The party-name text says "completa, sin anagrama(s)".

### Registry party-name fields

The published export layouts (`src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/export/*.toml`) were scanned on 2026-11-11 for binding, casilla and header fields that hold a party name.

- **Binding-row fields at offset 36, length 40, every edition listed:**
  - 156 `modelo-156-row-nombre` (2003-y-siguientes).
  - 180 `modelo-180-perceptor-row-name` (2019-2022, 2023-y-siguientes; record file `0002-record-modelo-180-perceptor.toml`).
  - 184 `modelo-184-member-row-name` (2023-2024, 2025-y-siguientes).
  - 190 `modelo-190-perceptor-row-name` (2022, 2023, 2024, 2025-y-siguientes).
  - 193 `modelo-193-perceptor-row-name` and `modelo-193-gasto-row-nombre` (2022-2025-y-siguientes).
  - 194 `modelo-194-perceptor-row-nombre` (2019, 2023, 2024).
  - 347 `modelo-347-contraparte-row-nombre` and `modelo-347-inmueble-row-arrendatario-nombre` (2011-2024, 2025-y-siguientes).
  - 720 `modelo-720.type_2.apellidos-y-nombre-razon-social-o-denominacion-del-declarado` (2013-y-siguientes).
- **349:** `iva-349-operador-row-apellidos` and `iva-349-rectificacion-row-apellidos`, offset 93, length 40 (2020-y-siguientes).
- **232:** the `matriz-razon-social` and `vinculada-metodo-1..3-razon-social` bindings, length 60.
- **390:** the representative and joint-declaration name bindings, lengths 37 and 80 (2022-2026).
- **Casilla-kind fields at offset 36, length 40:** 165 socio, 181, 185, 189, 280 and 345 declarado, 270 perceptor.
- **Declarant header:** `taxpayer.surnames_or_legal_name` (for example the 184 entidad record) and `taxpayer.full_name`.
- **Requirement:** every field listed is `required = false`. A missing name therefore exports as spaces.

### Where the names come from today

- **347 and 349 rows** read `party_legal_name`, which is set from `invoice.counterparty_name`, or from `collected_on_behalf_of_name` for third-party collection (`src/cadrumo/application/invoices/source_observations.py:288`, `:456`, `:472`). The bucket keeps the first observed name (`src/cadrumo/domain/calculations/registry/invoice_row_materialization.py:92-145`).
- **Facturae natural persons** are joined as Name, FirstSurname, SecondSurname, with the given name first (`src/cadrumo/adapters/inbound/einvoice/element_readers.py:99-117`).
- **190 and 193 perceptor names** come from `WithholdingObservation.perceptor_legal_name`, according to CALC-PAGOS's static reading as recorded in the ADR.
- **Over-width text** is refused by the codec's render length check (`src/cadrumo/domain/calculations/registry/fixed_width_codec.py:341-364`) with a generic error.
- **Per-entity store.** An operator-confirmed, per-entity, encrypted counterparty fact store exists: `ConfirmedCounterpartyFacts` (`src/cadrumo/application/ledger/counterparty_establishment.py:118-162`) and `CounterpartyEstablishmentRepository` (`src/cadrumo/adapters/persistence/profile/counterparty_establishment.py:34-43`).

### What the ADR must settle

- Whether the declared name is one string or typed components, given that the designs define the content as an ordered composition.
- Where the declaration lives.
- How a missing or over-width name refuses.
- How a natural person with no second surname is composed. No captured design states it.

## Sources

- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_347/files/01-347-ejercicio-2025-y-siguientes-modificados-p.pdf.extracted.md:272-284`, `:905-913`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_180/files/01-180-orden-hap-1732-2014-actualizado-por-orden.pdf.extracted.md:254-263`, `:444-449`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_190/files/01-190-orden-eha-3127-2009-de-10-de-noviembre-ac.pdf.extracted.md:88-98`, `:330-340`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_193/files/03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf.extracted.md:390-411`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/files/01-194-diseno-de-registro-actualizado-en-2024.pdf.extracted.md:60-69`, `:334`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_184/files/01-184-ejercicio-2025-y-siguientes-modificados-p.pdf.extracted.md:1848-1862`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_156/files/01-156-diseno-de-registro-vigente.pdf.extracted.md:166-169`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_349/files/01-349-orden-hac-174-2020-de-4-de-febrero-ejerci.pdf.extracted.md:52-58`, `:312-316`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_720/files/01-720-599-kb-pdf.pdf.extracted.md:115-124`, `:651-658`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/export/*.toml` (scan of 2026-11-11)
- `src/cadrumo/application/invoices/source_observations.py:288`, `:456`, `:472`
- `src/cadrumo/domain/calculations/registry/invoice_row_materialization.py:92-145`
- `src/cadrumo/adapters/inbound/einvoice/element_readers.py:99-117`
- `src/cadrumo/domain/calculations/registry/fixed_width_codec.py:341-364`
- `src/cadrumo/application/ledger/counterparty_establishment.py:118-162`
- `src/cadrumo/adapters/persistence/profile/counterparty_establishment.py:34-43`
