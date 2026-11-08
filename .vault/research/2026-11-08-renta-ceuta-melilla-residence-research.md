---
tags:
  - '#research'
  - '#renta-ceuta-melilla-residence'
date: '2026-11-08'
modified: '2026-11-08'
body_schema: 'body-v2'
body_hash: 'sha256:47c84cb3abecbe3e696f675aa96671ba37c4665ff9a95b02b414150acd64e3b6'
related: []
---

# `renta-ceuta-melilla-residence` research: `Ceuta and Melilla IRPF residence treatment`

Question: how does Modelo 100 treat a taxpayer resident in Ceuta or Melilla, and which of those facts must the residence axis carry?

## Findings

- **The record design codes both cities.** The AEAT Modelo 100 XSD `tipo_CCAA` simpleType declares "18" = CIUDAD DE CEUTA and "19" = CIUDAD DE MELILLA. The codes are identical in every bundled edition, 2020 through 2025, beside "20" = NO RESIDENTE.
- **The autonomic scale is art. 65.** LIRPF Disposición adicional trigésima segunda says verbatim: "La escala autonómica aplicable a los contribuyentes que tengan su residencia habitual en Ceuta o Melilla será la prevista en el artículo 65 de esta Ley." It was added by Ley 2/2011, published 05/03/2011 and in force 06/03/2011.
- **The art. 65 table has been constant since 2015.** Each row gives the base liquidable hasta, the cuota íntegra, the resto base and the tipo:
  - 0,00 / 0,00 / 12.450,00 / 9,50
  - 12.450,00 / 1.182,75 / 7.750,00 / 12,00
  - 20.200,00 / 2.112,75 / 15.000,00 / 15,00
  - 35.200,00 / 4.362,75 / 24.800,00 / 18,50
  - 60.000,00 / 8.950,75 / en adelante / 22,50

  It was last modified by Ley 26/2014 art. 1.41. The BOE consolidated text was read on 2026-11-08 at version 07/10/2026. Ley 11/2020 art. 58, effective 01/01/2021, amended art. 63.1 (the state scale, adding a 24,50 % band above 300.000) and not art. 65. The table is therefore one value for every supported year.
- **Worked check from the table.** Base 70.000 gives 8.950,75 + (70.000 − 60.000) × 22,5 % = 11.200,75. Base 30.000 gives 2.112,75 + (30.000 − 20.200) × 15 % = 3.582,75.
- **The autonomic mínimo falls back to the state amount.** Under LIRPF art. 56.3 the autonomic mínimo uses the amounts each comunidad approves under Ley 22/2009 art. 46.1.a, or else the state amounts of arts. 57 to 61. The cities approve none, so the state amounts apply. The registry already maps comunidades without an own amount to the state parameters.
- **No autonomic deducciones exist.** These are comunidad law (LIRPF art. 77, Ley 22/2009 art. 46), and the cities have none.
- **The 60 % art. 68.4 deduction is already modelled.** It applies to the portion of the cuotas íntegras attributable to rentas obtained in Ceuta or Melilla, with distinct resident (1.º) and non-resident (2.º) conditions. It sits on casillas 0560/0561 over 0727.
- **These are not foral territories.** Ceuta and Melilla are territorio común for IRPF and file Modelo 100. LIRPF art. 4.3 notes only that their specific rules (especialidades) apply.

## Sources

- AEAT Modelo 100 XSD designs, 2020 to 2025: `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/25-100-esquema-xsd-ejercicio-2020-*.xsd` through `28-*-2023-*.xsd` and `03-100-esquema-xsd-ejercicio-2025-*.xsd`, simpleType `tipo_CCAA`.
- Ley 35/2006 (LIRPF), bundled BOE extraction: `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md`, art. 65 and Disposición adicional trigésima segunda.
- BOE consolidated LIRPF, https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764: art. 65 table, and the art. 63 amendment note naming Ley 11/2020 art. 58.
- Ley 11/2020, https://www.boe.es/buscar/act.php?id=BOE-A-2020-17339.
