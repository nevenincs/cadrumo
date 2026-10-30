---
tags:
  - '#research'
  - '#assets-core'
date: '2026-10-30'
modified: '2026-10-30'
body_schema: 'body-v2'
body_hash: 'sha256:25362d97f4d593b0859e835bce4c129b77db17ebe5e49c2992dcb0332b7c2c8d'
related:
  - "[[2026-09-23-assets-core-amortization-method-set-research]]"
  - "[[2026-09-21-assets-core-lifecycle-and-integration-research]]"
---

# `assets-core` research: `IRPF amortization law, form placement and the capitalize-or-expense test`

Grounds the `assets-core` decisions on inmovilizado amortization and the libro registro de bienes de inversión. Researched 2026-10-30 from the bundled corpus under `src/cadrumo/_data/corpus/` and live BOE and AEAT pages. Current legal validity beyond those sources is not asserted. A finding is high confidence unless marked.

## Findings

### Amortization is an annual gasto that also enters each cumulative Modelo 130

The IRPF period is annual (LIRPF arts. 28.1, 30). RIRPF art. 110.1.a computes the pago fraccionado on rendimiento neto from 1 January to quarter end, and the Modelo 130 instructions place amortization inside casilla 02 for that span. There is no separate 130 casilla. Modelo 100 carries the annual dotación in 0208 (material) and 0227 (inmaterial), both inside 0218.

No statute prescribes a day count for the 130. Binding consulta V1978-24, cited in `2026-09-23-assets-core-amortization-method-set-adr`, and an AEAT libro registro FAQ (read through a summarising fetch) use days; a Renta 2025 manual example prorates by months (5/12). The Q4 cumulative must equal the annual dotación.

### Tables depend on regime, not on Comunidad Autónoma

Estimación directa normal uses LIS art. 12.1.a. Simplificada uses the Orden of 27 March 1998 (BOE-A-1998-7200) through RIRPF art. 30.1.ª, linear only for material. Estimación objetiva uses the annual módulos order: Orden HAC/1347/2024 for 2025, HAC/1425/2025 for 2026 (four general groups plus agrarian groups 5 to 10; forestry deducts none).

Autonomous powers over IRPF do not reach rendimiento determination (Ley 22/2009 art. 46; medium confidence on the enumeration). Residents of Navarra and the País Vasco file with their own Hacienda, so Modelo 100 does not apply (Ley 28/1990 art. 9, Ley 12/2002 art. 6). Their amortization tables were not read. Ceuta and Melilla change the 130 percentage to 8% (RIRPF art. 110.2) and Canarias adds the RIC (Ley 19/1994 art. 27.15); neither changes coefficients.

### Form placement

- Capital inmobiliario, per inmueble: 0131, 0132, 0117. Not activity casillas.
- Estimación directa: 0208, 0227; 0179 returns excess libertad amortization to income on disposal.
- Simplificada: 0222, 5% capped at 2,000 EUR, on a base net of amortization (RIRPF art. 30.2.ª).
- Módulos: 1467 non-agrarian (Minoración por incentivos a la inversión), 1538 agrarian.
- Disposal of afecto elements: 1654 summing to 0387; inmuebles 1843 summing to 1846 (medium-high).
- IVA, Modelos 303 and 390: acquisition in 30/31, 34/35, 38/39; regularización 43. This is not amortization.
- No per-asset schedule is filed in Modelos 100, 303, 390 or 200. Per-asset detail lives in the libro registro.

### Capitalize or expense

A durable element of inmovilizado is not a gasto corriente: only its annual depreciation deducts (LIS art. 12.1, RIS art. 3.2). Repairs and conservation are gastos; improvements are capitalized over remaining life (RIS art. 3.4). The legitimate immediate deduction is a libertad de amortización, which is still amortization and still 0208, not an expense line:

- LIS art. 12.3.e: new material, unit value up to 300 EUR, 25,000 EUR per period. Applies to all direct-estimation taxpayers through LIRPF art. 28.1, not only empresas de reducida dimensión.
- LIS art. 102: 120,000 EUR per unit of plantilla increase, with 24 plus 24 month conditions and clawback.
- LIS art. 103: twice the maximum coefficient, for reduced-size enterprises.
- LIS DA 17 and DA 18, LIRPF DA 59: renewables, electric vehicles and charging points. RDL 7/2026 art. 37 is the current text but reaches only periods not concluded at 22 March 2026, so it does not govern IRPF 2025. For 2025, DA 18 rests on RDL 4/2024, and DA 17 on RDL 16/2025 through the AEAT note of 1 April 2026, whose list does not name DA 17 (see `2026-09-23-assets-core-proration-and-incentive-scope-research`).
- Módulos has its own limit: new material up to 601.01 EUR unit value, 3,005.06 EUR per year.

A wrongly expensed purchase deducts more than the permitted amount. The excess is not deductible in that period (Renta 2025 manual). The IVA threshold of 3,005.06 EUR (LIVA art. 108) is unrelated to these limits.

### Basis, method and history

Basis is price plus costs up to puesta en funcionamiento, plus non-deductible IVA, excluding land (RIS art. 3.2). Amortization starts at puesta en condiciones de funcionamiento (RIS art. 3.3). Linear coefficients run between the maximum and 100 divided by maximum years, element by element (RIS art. 4.1). Used assets take up to twice the maximum on the acquisition price (RIS art. 4.3). Impairment of fixed assets is not deductible (LIS art. 13.2.a). Leasing is LIS art. 106. Passenger vehicles need exclusive use (RIRPF art. 22.4). Under-amortization catches up only through RIS art. 4.1, second paragraph.

### Disposal reduces cost by at least the minimum amortization

Transmission of an afecto element is a ganancia or pérdida patrimonial, outside rendimiento neto (LIRPF art. 28.2). Valor de adquisición falls by deductible amortization and in every case by the minimum amortization, claimed or not (RIRPF art. 40.1, 40.2). An unclaimed year therefore still reduces cost. Sale within three years of afectación undoes it (LIRPF art. 28.3).

### The register obligation

RIRPF art. 68 and Orden HAC/773/2019 (BOE-A-2019-10487, entries from 2020) require the IRPF libro registro de bienes de inversión. Fields, per element: invoice number, date in functioning condition, description, supplier and NIF, valor de adquisición and valor amortizable, method, percentage and quota per period, accumulated amortization, and baja with date and reason. The field lettering came through a paraphrase and must be re-read in BOE before encoding. The IVA book (RIVA art. 65) applies only where LIVA arts. 107 to 110 require regularización.

### Not verified

- DGT or TEAC criterion on unclaimed amortization and on wrongly expensed assets.
- Whether the 300 EUR value includes IVA, and how sets are counted.
- Foral tables and libertades.
- Whether RDL 7/2026 was convalidated (one secondary source).
- 130 treatment of the 2,000 EUR cap by quarter.
- Whether items up to 300 EUR must appear in the libro registro, and leasing entries before the option is exercised.
- No official worked example of a used asset was found. Twelve official worked examples for other cases exist and serve as independent oracles, including an accelerated part-year charge of 720, a leasing limit of 3,840, a módulos bar of 6,050 and an agrarian case of 11,185.

## Sources

- `normatives/html/ley-35-2006.html.extracted.md`, `rd-439-2007.html.extracted.md`, `ley-27-2014.html.extracted.md`, `ley-27-2014-art-12-full.html.extracted.md`, `rd-634-2015.html.extracted.md`, `ley-37-1992.html.extracted.md`, `rd-1624-1992.html.extracted.md`, `orden-hac-1347-2024.html.extracted.md`, `orden-hac-1425-2025.html.extracted.md`, `boe-a-2026-2024-derogacion-rdl-16-2025.html.extracted.md`, all under `src/cadrumo/_data/corpus/`.
- `manuals/renta/2025/part1/source.pdf.extracted.md`, `aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html` and the 2024 and 2025 dictionaries under `aeat_official/disenos_registro/modelo_100/files/`, under the same corpus root.
- https://www.boe.es/buscar/act.php?id=BOE-A-1998-7200
- https://www.boe.es/eli/es/o/2019/06/28/hac773/con
- https://www.boe.es/eli/es/l/2009/12/18/22/con
- https://www.boe.es/eli/es/l/2002/05/23/12/con
- https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/preguntas-frecuentes/libro-registro-bienes-inversion-iva-irpf.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Actualidad/Novedades/2026/BOLINFORM_RDL_7_2026.pdf
