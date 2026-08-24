---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8ffe957a21ede80d861d76bc1d2d990b04e92041faa1582ba2a40a420a4aef2f'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` reference: `modelo 188 design era coverage`

## Summary

Modelo 188 revision `2019-y-siguientes` is supported only as an
applicability-grade obligation. Cadrumo must not emit it for any selected year.
The sole shipped, hash-pinned AEAT record design is the 2023 edition. It
substantively post-dates 2019--2022 and so cannot evidence their byte layout.
For 2023 onwards, the design is an exact authoritative source but the product
still lacks the complete filing-value, semantic-map, generated-fragment, and
emitted-byte proof chain. A layout must not be inferred from the five summary
casillas.

## Official design eras

BOE-A-1999-22372 approves Modelo 188's physical and logical computer-readable
designs in its Annex V. Subsequent amendments change real type-2 record
content. BOE-A-2017-15845 changes `INFORMACIÓN ADICIONAL` at positions 92--104,
`% RETENCIÓN` at positions 131--134, and `CLAVE` at position 152; its final
provision makes those changes first applicable to exercise 2017. That is the
known statutory baseline for the 2019--2022 period, not proof that the later
2023 layout has the same bytes.

BOE-A-2023-24412 Article 5 changes Modelo 188's type-1 declarant NIF at
positions 9--17 and type-2 perceptor NIF, legal-representative NIF, and
province fields at positions 18--26, 27--35, and 76--77. Its final provision
applies the order first to declarations for exercise 2023, presented in 2024.
Those changes establish a real design-era boundary: the 2023 layout cannot be
backdated to a 2019--2022 declaration.

The current AEAT design catalogue continues to publish Modelo 188 as the 2007
order updated by Orden HFP/1284/2023. The shipped PDF is 106,418 bytes with
SHA-256 `30ced236b558de21383c3eba6339cb720fc9a704d38eaa574dd9be55cf90f9e3`;
its source declaration, `aeat-dr-188-2023`, begins on 2023-01-01 and has no
end date. It is therefore the presently selected source only for the 2023-plus
era. The catalogue does not turn it into a historical 2019 design.

AEAT's current Modelo 188 procedure exposes a 2025 filing-by-file route and
consultation or cancellation routes for 2020 onwards. A live portal route
confirms that an AEAT filing surface exists; it neither supplies the historic
field table nor validates a Cadrumo export.

## Current shipped boundary

The loaded `2019-y-siguientes` revision declares `authority_grade =
"applicability"`, five manual `resumen` casillas, no formulas, and no export
layout. It cites the 2023 source but its period selector starts in 2019. The
derived filing-capability worklist correctly refuses it on design coverage for
2019--2022. Its `m188` producer namespace is also absent from
`FilingProducerKey`, so neither the type-1 declaration fields nor the complete
perceptor rows have a legitimate value-owner vocabulary for a semantic map.

`test_modelo_188_resumen_matches_its_design.py` checks only that the five
summary boxes agree with the 2023 PDF's summary widths and stated count offsets.
It does not identify every type-1/type-2 field, establish a historic design,
or supply a renderer. Treating that narrow parity test as layout authority
would fabricate a filing claim.

**Disposition: retain the whole revision at applicability grade with no export
layout and no filing capability.** The exact supported filing-design boundary is
currently 2023 onwards as source evidence only; the exact fileable boundary is
empty for every selected exercise. This preserves the law-selected obligation
while refusing any output whose record-era or value provenance is incomplete.

## Owner and reconsideration

`W02.P04.S26` must enroll the temporal remedy in
`2026-08-14-registry-temporal-coverage-plan`: acquire and hash-pin an exact
official design for every 2019--2022 exercise, or a reviewed primary BOE
Annex-V-plus-amendments composite with an explicit exercise scope; then split
or constrain revision selection so every selected year cites a governing era.
The 2023 design must not be backdated.

`W02.P04.S28` must enroll the export remedy in
`2026-08-10-aeat-export-fragment-generator-authority-plan`: assign every
type-1 and type-2 field to a live provenance-carrying producer, create the
reviewed semantic map and render profile, generate through the canonical
publisher, and prove production bytes at official offsets. If this exposes a
new external value source, `W02.P04.S27` must first enroll its lifecycle and
provenance in `2026-08-22-source-casilla-integration-plan`; an export map may
not impersonate a source owner.

Reconsider fileability only after all selected years have immutable official
record-design authority; the actual insurer or other obligated filer population
and every value owner are approved; every selected design has a complete
reviewed map; and canonical generated fragments and real emitted-byte proof
pass. Only then may a bounded selected revision be considered for filing grade.
This adjudication authorizes neither a compatibility layout nor remote AEAT
submission.

## Sources

- BOE-A-1999-22372, Orden de 17 de noviembre de 1999, apartado sexto and
  Annex V, retrieved 2026-08-24: https://www.boe.es/buscar/doc.php?id=BOE-A-1999-22372
- BOE-A-2017-15845, Orden HFP/1308/2017, article 3 and final provision,
  retrieved 2026-08-24: https://www.boe.es/buscar/doc.php?id=BOE-A-2017-15845
- BOE-A-2023-24412, Orden HFP/1284/2023, article 5 and final provision,
  retrieved 2026-08-24: https://www.boe.es/buscar/doc.php?id=BOE-A-2023-24412
- AEAT current record-design catalogue, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- AEAT current Modelo 188 procedure, retrieved 2026-08-24:
  https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI08.shtml
- `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2019-y-siguientes/`
- `src/cadrumo/_data/registry/aeat/legal/enrolled-forms-sources.toml`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_188/manifest.json`
- `src/cadrumo/domain/calculations/registry/tests/test_filing_capability_worklist.py`
- `src/cadrumo/domain/calculations/registry/tests/test_modelo_188_resumen_matches_its_design.py`
- `2026-08-14-registry-temporal-coverage-plan`
- `2026-08-22-source-casilla-integration-plan`
- `2026-08-10-aeat-export-fragment-generator-authority-plan`
