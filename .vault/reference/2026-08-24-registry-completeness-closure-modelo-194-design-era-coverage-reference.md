---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:82ab3f9f4b1dc44defa7b3314c71d867f1c02ee5e622b67db9a4fa23dc9c82dc'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` reference: `modelo 194 design era coverage`

## Summary

Modelo 194 revision `2019-y-siguientes` remains an applicability-grade
obligation only. Cadrumo must not emit it for any selected exercise. Its one
law-selected revision begins in 2019, while the shipped corpus hash-pins only
the 2023 and 2024 AEAT record designs. The first missing era is not
speculative: AEAT still exposes an exact 2019 record design, and the BOE
records the change that made it applicable to the 2019 declaration. It has
not been acquired, hash-pinned, registered, or connected to the revision.

The exact filing boundary is therefore empty. The 2023 and 2024 PDFs establish
that official layouts exist for those individual exercises, but the revision
has no complete type-1/type-2 value ownership, semantic map, generated export
fragments, or emitted-byte proof. A summary of five manual casillas cannot
stand in for the two record types.

## Official design eras

The AEAT historic 100--199 design catalogue exposes `DR194_2016.pdf`; despite
its storage name, the document cover and all record pages identify it as
`Ejercicio 2019`. It is an exact 2019 field table, including the type-1
declarant record and type-2 perceptor record. BOE-A-2019-18752 changes
Modelo 194's Annex X, including the type-2 `VALOR TRANSMISIÓN, AMORTIZACIÓN,
REEMBOLSO, CANJE O CONVERSIÓN` field at positions 131--143. Its final
provision says that the order first applies to declarations for exercise 2019,
filed in 2020.

BOE's official amendment history for the 1999 approving order lists the next
Annex-X changes as BOE-A-2023-24412 and BOE-A-2024-27528. BOE-A-2023-24412
changes real Modelo 194 record fields, including type-1/type-2 NIF fields and
the type-2 province and retention-related fields; its final provision first
applies to exercise 2023. The shipped `aeat-dr-194-2023` PDF says `Ejercicio
2023`, has SHA-256 `83cd9a332e0016607e87332bea8c3e5d33f0b0f8373ec56f820d82414ca76a7b`,
and the source catalogue scopes it from 2023 through 2023.

BOE-A-2024-27528 changes type-1 `TIPO DE SOPORTE`, the prior-declaration
receipt field, and the type-2 retention percentage. Its final provision first
applies to exercise 2024. The AEAT current design catalogue exposes the
matching `Ejercicio 2024` PDF; the shipped `aeat-dr-194-2024` artifact has
SHA-256 `4a738a126ddb465aac236b687aa25441b7cb71ec4b0ef6ea940096a3747b2651`.
The source catalogue scopes that artifact from 2024 without a closing date,
but the PDF itself names only exercise 2024. Current-catalogue presence is not
a blank cheque to infer an unevidenced later design; retain the ordinary
source-expiry and exact-year checks.

The AEAT filing procedure exposes historical presentation for exercises 2020
through 2024 and consultation or cancellation from 2020 onward. That confirms
an AEAT filing surface, not that Cadrumo has the required values or a valid
byte layout.

## Shipped and fileable boundary

The loaded registry selects `2019-y-siguientes` from 2019, retains
`authority_grade = "applicability"`, declares only manual summary casillas
`01` through `05`, and has no export layout. Its source references include the
2023 and 2024 record designs but no 2019 record-design source. The current
capability worklist consequently refuses it on design coverage: a 2023 or 2024
source cannot evidence the selected 2019--2022 years.

The source shortfall is necessary but not sufficient. There is no `m194.`
`FilingProducerKey` namespace, no committed Modelo 194 mapping or render
profile, and no declared export layout. The five summary casillas prove only
the printed summary boxes; both AEAT designs require a full declarant record
and one perceptor record per declared person. Creating a layout from those
five boxes would invent every non-casilla field and silently drop perceptor
data.

**Disposition: retain the revision at applicability grade with no export
layout and no filing capability.** The supported obligation boundary remains
the registry's 2019-and-later selection. The record-design evidence boundary
is: exact 2019 authority available externally but not yet enrolled; exact 2023
and 2024 authority bundled and hash-pinned; no evidence in this Step that a
single layout may be used beyond the documented era. The fileable boundary is
empty for every selected year.

## Owner and reconsideration

`W02.P04.S26` must enroll the temporal remedy in
`2026-08-14-registry-temporal-coverage-plan`: acquire the AEAT 2019 PDF at
its recorded official URL, hash-pin and register it with an evidence-backed
2019--2022 scope, or acquire exact per-year replacements; validate the
2019-to-2023 transition against BOE-A-2019-18752 and BOE-A-2023-24412. It
must also keep the 2024 successor distinct and constrain any open-ended source
claim to evidence actually available at publication time.

`W02.P04.S28` must enroll the export remedy in
`2026-08-10-aeat-export-fragment-generator-authority-plan`: approve the actual
filer population, assign all type-1 and type-2 values to provenance-carrying
producers, create a reviewed semantic map and render profile for each selected
design era, generate through the canonical publisher, and prove production
bytes at official offsets. If a required perceptor or asset value has no
existing governed lifecycle, `W02.P04.S27` must first enroll that source and
provenance work in `2026-08-22-source-casilla-integration-plan`.

Reconsider filing grade only after every selected exercise has immutable
official record-design authority, all full-record value owners and the filer
population are approved, each era has a complete reviewed map, and canonical
generated fragments plus real emitted-byte evidence pass. This adjudication
does not authorize a compatibility layout, a grade promotion, or remote AEAT
submission.

## Sources

- BOE-A-1999-22309, Orden de 18 de noviembre de 1999, Annex X and official
  amendment history, retrieved 2026-08-24:
  https://www.boe.es/buscar/doc.php?id=BOE-A-1999-22309
- BOE-A-2019-18752, Orden HAC/1276/2019, article one and final provision,
  retrieved 2026-08-24:
  https://www.boe.es/buscar/doc.php?id=BOE-A-2019-18752
- BOE-A-2023-24412, Orden HFP/1284/2023, article 6 and final provision,
  retrieved 2026-08-24:
  https://www.boe.es/buscar/doc.php?id=BOE-A-2023-24412
- BOE-A-2024-27528, Orden HAC/1504/2024, article one and final provision,
  retrieved 2026-08-24:
  https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-27528
- AEAT current record-design catalogue, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- AEAT historic 100--199 design catalogue and exact Modelo 194 2019 design,
  retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/ejercicios-anteriores-modelos-100-199.html
  https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos/DR194_2016.pdf
- AEAT Modelo 194 historical filing procedure, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/declaraciones-informativas/modelo-194-decla_____n-utilizacion-capitales-anual/ejercicios-anteriores.html
- `src/cadrumo/_data/registry/aeat/modelos/194/revisions/2019-y-siguientes/`
- `src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_194/manifest.json`
- `src/cadrumo/core/_filing_producer_key.py`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_187_188_194_registry.py`
- `2026-08-14-registry-temporal-coverage-plan`
- `2026-08-22-source-casilla-integration-plan`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`
