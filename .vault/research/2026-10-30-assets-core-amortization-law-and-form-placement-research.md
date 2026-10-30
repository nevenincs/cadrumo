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

The IRPF period is annual (LIRPF arts. 28.1, 30). RIRPF art. 110.1.a computes the pago fraccionado on rendimiento neto from 1 January to quarter end, and the Modelo 130 instructions place amortization inside casilla 02 for that span. There is no separate 130 casilla. The exception is agrarian: agrícola, ganadera, forestal and pesquera activities pay 2% of ingresos "cualquiera que fuese el método" (RIRPF art. 110.1.c; 0.8% in Ceuta and Melilla), so their amortization never enters the pago fraccionado. It still enters Modelo 100. Modelo 100 carries the annual dotación in 0208 (material) and 0227 (inmaterial), both inside 0218.

No statute prescribes a day count, and the official sources diverge. Consulta V1978-24 (17/09/2024) orders proration by days of operation over days of the year, but it concerns módulos (Orden HAC/1359/2023, anexo II, instrucción 2.2.b) and the first year's annual quota, not estimación directa and not quarters. V0698-21 applies days to a fixed percentage for rented property at disposal. The AEAT libro registro FAQ applies days in use in the quarter over days in the year. The Renta 2025 manual prorates estimación directa by months: 720 for a machine in service on 1 December (1/12) and 3,840 for a van from 1 July (6/12). Days would give 733.81 in the first case. No source says how to reconcile them for estimación directa. The Q4 cumulative must equal the annual dotación.

### Tables depend on regime, not on Comunidad Autónoma

Estimación directa normal uses LIS art. 12.1.a. Simplificada uses the Orden of 27 March 1998 (BOE-A-1998-7200) through RIRPF art. 30.1.ª, linear only for material. Estimación objetiva uses the annual módulos order: Orden HAC/1347/2024 for 2025, HAC/1425/2025 for 2026 (four general groups plus agrarian groups 5 to 10; forestry deducts none).

Autonomous powers over IRPF do not reach rendimiento determination (Ley 22/2009 art. 46.1.a to d). Residents of Navarra and the País Vasco file with their own Hacienda, so Modelo 100 does not apply (Ley 28/1990 art. 9, Ley 12/2002 art. 6). Their amortization tables were not read. Ceuta and Melilla change the 130 percentage to 8% (RIRPF art. 110.2) and Canarias adds the RIC (Ley 19/1994 art. 27.15); neither changes coefficients.

### Form placement

- Capital inmobiliario, per inmueble: 0131, 0132, 0117. Not activity casillas.
- Estimación directa: 0208, 0227; 0179 returns excess libertad amortization to income on disposal. The dictionary label names only LIRPF DA 30, but the Renta 2025 manual's ingresos section with the same heading cites DA 30 and DA 59 together (part 1, lines 17462-17484), so the DA 59 excess goes there in estimación directa. Its placement for módulos was not found.
- Simplificada: 0222, 5% capped at 2,000 EUR, on a base net of amortization (RIRPF art. 30.2.ª). The rate was 7% for 2023 only (LIRPF DA 56).
- Módulos: 1467 non-agrarian (Minoración por incentivos a la inversión), 1538 agrarian.
- Disposal of afecto elements: 1654 summing to 0387; inmuebles 1843 summing to 1846.
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

The amortizable amount is the precio de adquisición or coste de producción, less any valor residual, excluding land (RIS art. 3.2). RIS art. 3.2 does not mention IVA: non-deductible IVA enters through PGC NRV 12.ª, which also says regularizations under the prorrata, including those for bienes de inversión, do not alter the initial valuation (quoted in V2454-11 and V1066-19, both Impuesto sobre Sociedades, and reaching IRPF through LIRPF art. 28.1). V2454-11 separates that from an inspection correcting a wrong deduction, which does restate the asset's value. Amortization starts at puesta en condiciones de funcionamiento (RIS art. 3.3). Linear coefficients run between the maximum and 100 divided by maximum years, element by element (RIS art. 4.1). Used assets take up to twice the maximum on the acquisition price, or the maximum on the original price where known, or on an expert valuation where not (RIS art. 4.3.a to c); the rule has a group exception and treats buildings under 10 years as new. Impairment of fixed assets is not deductible (LIS art. 13.2.a). Leasing is LIS art. 106. Passenger vehicles need exclusive use (RIRPF art. 22.4). RIS art. 4.1, second paragraph, is not a general catch-up: it attributes a later accounting excess over the maximum to the earlier under-amortized year, up to that year's minimum, for the purposes of LIS art. 11.3.1.º.

### Disposal reduces cost by at least the minimum amortization

Transmission of an afecto element is a ganancia or pérdida patrimonial, outside rendimiento neto (LIRPF art. 28.2). Valor de adquisición falls by deductible amortization and in every case by the minimum amortization, claimed or not (RIRPF art. 40.1, 40.2). An unclaimed year therefore still reduces cost. Sale within three years of afectación undoes it (LIRPF art. 28.3).

### The register obligation

RIRPF art. 68 and Orden HAC/773/2019 (BOE-A-2019-10487, entries from 2020) require the IRPF libro registro de bienes de inversión. Fields, per element: invoice number, date in functioning condition, description, supplier and NIF, valor de adquisición and valor amortizable, method, percentage and quota per period, accumulated amortization, and baja with date and reason. The fields were read against art. 4.3.a to h, also quoted in V2498-24. Art. 4.1 covers "los elementos patrimoniales afectos" with no value threshold, so an item up to 300 EUR is entered. The IVA book (RIVA art. 65) applies only where LIVA arts. 107 to 110 require regularización.

### DGT doctrine on the open questions

Read in the DGT database, binding consultas.

- Asset or gasto: the LIS has no definition of inmovilizado, so the PGC governs: activo no corriente is what serves "de forma duradera" (V0764-23, V1332-23). A laptop is inmovilizado deducted through amortization (V3667-16), as is a camera (V2498-24). No source sets a value floor. PGC importancia relativa is an accounting principle; no consulta applying it to IRPF was found.
- Omission from Modelo 130: V1031-14 holds that omitting the 5% from the 130 does not prevent deducting it in the annual return, "sin perjuicio de las rectificaciones" of the 130. No source addresses amortization by quarter or a choice to defer it.
- Unclaimed amortization at disposal: cost falls by the minimum "con independencia de la efectiva consideración de ésta como gasto" (RIRPF art. 40.1; V3655-16, V0698-21, V0550-22). A fully elapsed period leaves value zero (V3655-16).
- Late deduction: LIS art. 11.3.1.º imputes a gasto booked late to the booking year unless that lowers tax. Rectification runs through LGT arts. 120.3 and 221.4 and RGAT art. 126, with the interés legítimo left to AEAT (V1994-20, a rented home under-amortized through an error of base). No consulta on an activity taxpayer who skipped a year was found.
- Home in part use: only a part with separate and independent use may be afectada (RIRPF art. 22.3). Amortization applies in proportion to the part afectada (V3667-16, V0229-20) and to the ownership share (V1918-10). The base is the valor de adquisición excluding land, starting when the part goes into use (V0229-20). The value on later afectación is the valor de adquisición under LIRPF arts. 35.1 and 36 (RIRPF art. 23.1).
- Baja: theft of an afecto vehicle is a ganancia or pérdida patrimonial, indemnity less net book value with fiscally deductible amortizations (V2285-14). Handing a fully amortized tractor in part exchange gives value zero (V2639-13). No consulta on scrapping was found.
- Disposal rules: only LIRPF DA 30.2 and DA 59.2 carve out the excess. LIS arts. 102 and 103 contain none; art. 102.4 is a workforce clawback.

### Rulings for implementation

Each rule below is what the product implements. Precedence is statute and regulation, then binding DGT consulta (LGT art. 89.1) and TEAC unification, then AEAT guidance. A manual example does not displace a higher source.

- Day count: days of operation over days of the year, for every method. RIS art. 4.1 makes the coefficient a corridor, so the days figure is the maximum and any lower amount down to the minimum is lawful. The manual's 720 lies inside the 733.81 maximum, so months and days do not conflict: 720 is an admissible claim, not the ceiling.
- Modelo 130: casilla 02 carries the amortization accrued from 1 January to quarter end, computed from the element (RIRPF art. 110.1.a), excluding agrarian activities. A missing claim does not block; a later annual deduction remains available (V1031-14).
- 2,000 EUR cap: 5% of cumulative net return, capped at 2,000 EUR cumulatively. RIRPF art. 30.2.ª sets an annual cap and art. 110.1.a computes cumulatively, so the cap is not divided by quarter.
- Skipped year: each year's deduction stays limited to that year's maximum, and the minimum still reduces cost. An ordinary amortization may be corrected for its own year within prescription (LGT arts. 120.3, 221.4), recorded locally and never submitted by the product. A libertad not taken in a return cannot be taken later for that year by rectification, though it stays available in later years (TEAC 01524/2017, 14/02/2019, as reported by SuperContable, based on LGT art. 119.3). The manual says an excess over the permitted figure "pueda serlo en períodos posteriores", which stays within those maximums.
- 300 EUR: the valor unitario is the precio de adquisición under NRV 12.ª, so it includes non-deductible IVA and excludes deductible IVA.
- Scrapping: baja with zero proceeds, a pérdida patrimonial of the net value under LIRPF art. 33.1, computed as in V2285-14 and V1161-19 (fire, baja at destruction).
- Later afectación: RIRPF art. 23.1 sets the value without deemed amortization for private years; amortization starts at afectación.
- Leasing: not entered in the libro until the option is exercised, because RIRPF art. 22.2 and Orden HAC/773/2019 art. 4.1 address elementos of the taxpayer's patrimony. Cuotas follow LIS art. 106.
- DA 59 excess under módulos: DA 59.2 makes it rendimiento íntegro whatever the method, and that method's addition line is 1478 Otras percepciones empresariales (manual, part 1, line 22058). This placement is derived, as no source names the casilla.
- Foral residents: refused, because Modelo 100 and 130 of the AEAT do not apply to them (Concierto art. 6, Convenio art. 9).
- Accumulated limit: amortization never exceeds the amortizable value (V2498-24; TEAC RG 653/2025, 18/12/2025, for rented property, reported by secondary sources and not read in the original).

### Not read in the original

- TEAC 01524/2017 and RG 653/2025, read through secondary reports.
- BOE resolution convalidating RDL 7/2026, reported by INAP as dated 26 March 2026.
- Foral tables, because foral residents are refused.
- No official worked example of a used asset was found. Twelve official worked examples for other cases exist and serve as independent oracles, including an accelerated part-year charge of 720, a leasing limit of 3,840, a módulos bar of 6,050 and an agrarian case of 11,185.

## Sources

- `normatives/html/ley-35-2006.html.extracted.md`, `rd-439-2007.html.extracted.md`, `ley-27-2014.html.extracted.md`, `ley-27-2014-art-12-full.html.extracted.md`, `rd-634-2015.html.extracted.md`, `ley-37-1992.html.extracted.md`, `rd-1624-1992.html.extracted.md`, `orden-hac-1347-2024.html.extracted.md`, `orden-hac-1425-2025.html.extracted.md`, `boe-a-2026-2024-derogacion-rdl-16-2025.html.extracted.md`, all under `src/cadrumo/_data/corpus/`.
- `manuals/renta/2025/part1/source.pdf.extracted.md`, `aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html` and the 2024 and 2025 dictionaries under `aeat_official/disenos_registro/modelo_100/files/`, under the same corpus root.
- https://www.boe.es/buscar/act.php?id=BOE-A-1998-7200
- https://www.boe.es/buscar/act.php?id=BOE-A-2007-19884
- https://petete.tributos.hacienda.gob.es/consultas (V1978-24, V1031-14, V3667-16, V0229-20, V1918-10, V0698-21, V0550-22, V3655-16, V1994-20, V2285-14, V2639-13, V2498-24, V0764-23, V1332-23, V2454-11, V1066-19)
- https://www.boe.es/eli/es/o/2019/06/28/hac773/con
- https://www.boe.es/eli/es/l/2009/12/18/22/con
- https://www.boe.es/eli/es/l/2002/05/23/12/con
- https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/preguntas-frecuentes/libro-registro-bienes-inversion-iva-irpf.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Actualidad/Novedades/2026/BOLINFORM_RDL_7_2026.pdf
