---
tags:
  - '#research'
  - '#profile-field-remap'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:9b5135e51df34c22741ead29371881e6511aa5f2c5c5635dbef754bb4f94ccb5'
related:
  - '[[2026-10-27-profile-field-remap-iva-home-office-suministros-research]]'
  - '[[2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research]]'
---
# `profile-field-remap` research: `Category deductibility rules audit against bundled official sources`

Question (plan Step S12): which deductibility rules served from the category registry facts `categories.profile` (`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml`) and `categories.statutory-cap` (`src/cadrumo/_data/registry/aeat/facts/0065-categories-statutory-cap.toml`), and which locale wording served with them, contradict the bundled official sources or the statute, for filing years 2022 to 2026?

Conclusion: the 42 categories carry identical non-citation attributes in all five yearly variants, so every finding below spans 2022 to 2026 unless a year is named. The numeric caps are right in every year: dietas, seguro de enfermedad, and the yearly mutualidad schedule. Six categories have a wrong IRPF kind: five vehicle categories and `telefonia_movil` are modelled as a partial usage ratio, and the law allows no partial affectation for them. Two more (`hardware_amortizable`, `mobiliario_amortizable`) deduct the purchase price instead of the amortization quota. `manutencion_dietas_nacional` has a wrong `iva_hint`. The IVA mixed-use treatment is missing for every category except the six that Step S11 already covers, and LIVA art. 95 denies the row-share deduction that the code applies to them. Locale wording misstates the law for the mutualidad cap, the seguro de enfermedad cap, the rule numbers, the tributos citation and the dietas label. Thirty-four 2025 Manual de Renta citations are marked `source_not_bundled` although the manual is bundled. Four code behaviors change the outcome of the cap and exclusive-use rules and are listed apart (F16).

Not investigated: foral territories; estimacion objetiva; special IVA regimes (recargo de equivalencia, agricultura), where non-recoverable IVA joins the IRPF base; the casilla routing facts (`modelo-100-first-slice-expense-routing-mapping`); DGT, TEAC and court originals (none bundled); the Manual practico IVA 2022 to 2024 editions for the vehicle and hostelería rules (only 2025 read); whether IRPF allows a business share for expenses in `full_deductible` categories that are not assets (the sources read do not say). The executor of Step S11 edited `0064-categories-profile.toml` (7645 lines when first read, 8598 when last read) and `src/cadrumo/locales/*/common.yml` while this audit ran. Line numbers are as last read on 2026-10-27; locate a variant by its `variant_id`.

## Findings

### F01 Vehicle running costs are a usage ratio in the registry; the IRPF rule is exclusive use

- Categories and years: `vehiculo_combustible`, `vehiculo_mantenimiento`, `vehiculo_seguro`, `vehiculo_peaje`, `vehiculo_parking`; 2022 to 2026.
- Current: `proportionality_kind = "usage_ratio_personal"`, at `0064-categories-profile.toml:4237,4270,4303,4336,4376` (combustible), `:4409,4442,4475,4508,4548` (mantenimiento), `:4581,4614,4647,4680,4720` (seguro), `:4753,4786,4819,4852,4892` (peaje), `:4925,4958,4991,5024,5064` (parking).
- Correct: `requires_exclusive_use`. A turismo, remolque, ciclomotor or motocicleta is an affected asset only if used exclusively for the activity. Private use, even accessory, defeats affectation, except for the five listed uses of RIRPF art. 22.4 (a) to (e), which tolerate accessory private use on non-working time. An indivisible asset admits no partial affectation. No business-use share exists. The registry notes and citations already say "afectacion exclusiva"; only the kind contradicts them.
- Source: RIRPF art. 22.2.1, 22.3 and 22.4 (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:473,475,477`); LIRPF art. 29.2 (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:492`); Manual practico Renta 2025 (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:15793-15801,15821-15828`), same text in the 2022, 2023 and 2024 editions (`manuals/renta/2022/part1/source.pdf.extracted.md:12825-12830`, `manuals/renta/2023/part1/source.pdf.extracted.md:14965`, `manuals/renta/2024/part1/source.pdf.extracted.md:15499`). The asset register of this repository states the same rule (`src/cadrumo/domain/renta/actividad_asset/vehicle_affectation.py:1-10,105-125`).
- Confidence: high.
- Read in production: yes. The kind selects the evaluator (`src/cadrumo/domain/renta/ledger_expenses.py:571-586`), puts the category in the user-ratio set (`src/cadrumo/domain/usage_ratios/model.py:93`) that the Ratios pane lists (`src/cadrumo/application/ledger/ratios.py:120-131`), and reaches the LLM classifier prompt as `[usage_ratio_personal]` (`src/cadrumo/domain/transactions/llm.py:467-498`). Today a MIXED vehicle row deducts its stored ratio.

### F02 `telefonia_movil` is a usage ratio in the registry; the IRPF rule is exclusive use

- Categories and years: `telefonia_movil`; 2022 to 2026.
- Current: `proportionality_kind = "usage_ratio_personal"` at `0064-categories-profile.toml:2726,2790,2854,2918,2986`.
- Correct: `requires_exclusive_use`. The line is deductible "en la medida en que esta linea se utilice exclusivamente para el desarrollo de la actividad economica". The handset is deducted by amortization. The registry note already says "afectacion exclusiva".
- Source: Manual practico Renta 2025 (`manuals/renta/2025/part1/source.pdf.extracted.md:18153-18163`); same sentence in 2022 (`manuals/renta/2022/part1/source.pdf.extracted.md:14965-14969`), 2023 (`manuals/renta/2023/part1/source.pdf.extracted.md:17260`) and 2024 (`manuals/renta/2024/part1/source.pdf.extracted.md:17925`). The IVA side is in F09.
- Confidence: high.
- Read in production: yes, as for F01.

### F03 `hardware_amortizable` and `mobiliario_amortizable` deduct the purchase price in the year of purchase

- Categories and years: `hardware_amortizable`, `mobiliario_amortizable`; 2022 to 2026.
- Current: `proportionality_kind = "full_deductible"` at `0064-categories-profile.toml:3721,3754,3787,3820,3860` and `:3893,3926,3959,3992,4032`. Both route to the amortization casilla 0208 (`src/cadrumo/_data/registry/aeat/facts/2025/mapping/0090-2025-modelo-100-first-slice-expense-routing-mapping.toml:133-134`). The evaluator deducts the whole base (`ledger_expenses.py:439-451`). The register withholds a purchase only when a registered asset names the transaction as its acquisition (`src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py:135-197`). Without a registered asset the full price enters casilla 0208 in the purchase year.
- Correct: the deductible item is the yearly amortization quota (LIS art. 12.1). Normal modality: equipos para procesos de informacion 25 per cent, 8 years; sistemas y programas informaticos 33 per cent, 6 years; mobiliario 10 per cent, 20 years. Simplified modality: IT equipment and software 26 per cent, 10 years; mobiliario 10 per cent, 20 years. New assets of an empresa de reducida dimension may use double the maximum linear coefficient. New items of unit value up to 300 EUR may be written off freely, up to 25,000 EUR per period.
- Source: `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-12-full.html.extracted.md:80-81,103-106,137`; RIRPF art. 30 regla 1.a (`rd-439-2007.html.extracted.md:544`); Manual practico Renta 2025 (`manuals/renta/2025/part1/source.pdf.extracted.md:18654-18665,19136-19170,19442-19447`).
- Confidence: medium. The rule is clear. What the category is meant to hold (a purchase or a quota) is not stated; the es note says "totalmente deducible mediante amortizacion" (`src/cadrumo/locales/es/common.yml:398-401`). The ADR must settle: purchases that need a register asset before they deduct, or quotas entered directly.
- Read in production: yes (kind, routing, register).

### F04 No category implements the 1 per cent cap on atenciones a clientes

- Categories and years: `publicidad_marketing` is the nearest home (the Manual lists "Publicidad, propaganda y relaciones publicas" under otros servicios exteriores); 2022 to 2026. No category named for atenciones exists among the 42.
- Current: `proportionality_kind = "full_deductible"` at `0064-categories-profile.toml:6101,6134,6167,6200,6240`; es note "Gasto totalmente deducible" (`src/cadrumo/locales/es/common.yml:446-449`). A search of `src` outside the corpus finds no code or registry handling of the cap.
- Correct: atenciones a clientes o proveedores are deductible up to 1 per cent of the importe neto de la cifra de negocios of the period. The IVA on them is not deductible in any proportion (LIVA art. 96.Uno.5).
- Source: LIS art. 15.e (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-15.html.extracted.md:8`); Manual practico Renta 2025 (`manuals/renta/2025/part1/source.pdf.extracted.md:18233-18241`; same sentence in 2022 `manuals/renta/2022/part1/source.pdf.extracted.md:15055`, 2023 `manuals/renta/2023/part1/source.pdf.extracted.md:17343`, 2024 `manuals/renta/2024/part1/source.pdf.extracted.md:18008`); LIVA art. 96.Uno.5 (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2301`).
- Confidence: high on the law; medium on whether the fix is a new category or a note, since no source says where an operator should record such rows.
- Read in production: not applicable (the datum is absent).

### F05 Home-ownership expenses omit the co-ownership share

- Categories and years: `amortizacion_vivienda_afecto`, `ibi_vivienda_afecto`, `comunidad_vivienda_afecto`; 2022 to 2026.
- Current: `usage_ratio_home_area` with no multiplier, at `0064-categories-profile.toml:8018,8051,8084,8117,8157`, `:8190,8223,8256,8289,8329` and `:8362,8480,8513,8546,8586`. The stored ratio is area only (`src/cadrumo/domain/usage_ratios/service.py:186`).
- Correct: these expenses are deductible "en proporcion a la parte de la vivienda afectada al desarrollo de la actividad y a su porcentaje de titularidad en el inmueble". The no-multiplier choice is right: the 30 per cent factor is limited to suministros. A co-owned dwelling over-deducts by the share of the other owners.
- Source: Manual practico Renta 2025 (`manuals/renta/2025/part1/source.pdf.extracted.md:15842-15846`); the 30 per cent limit to suministros is LIRPF art. 30.2.5.b (`ley-35-2006.html.extracted.md:510`).
- Confidence: medium. The Manual states it; no other source read does, and the registry has no datum for ownership.
- Read in production: absent.

### F06 `manutencion_dietas_nacional` is hinted as exempt or not subject; restaurants charge IVA

- Categories and years: `manutencion_dietas_nacional`; 2022 to 2026. Already recorded in research stem `2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research`; not on the S11 list.
- Current: `iva_hint = "exempt_or_non_subject"` at `0064-categories-profile.toml:5102,5151,5200,5249,5297`.
- Correct: `general`. Hostelería and restauración are taxed at the reduced rate. The input cuota is deductible only when the expense is fiscally deductible in IRPF (the capped dieta), so the IVA follows the IRPF cap. Applying that to the own meals of the autónomo is an inference from the statute text; no DGT reply was read.
- `manutencion_dietas_extranjero` carries the same hint. Foreign VAT lies outside the Spanish return, so the hint is defensible. Confidence there is low either way.
- Source: LIVA art. 91.Uno.2.2 (`ley-37-1992.html.extracted.md:2102`); LIVA art. 96.Uno.6 (`ley-37-1992.html.extracted.md:2305`); Manual practico IVA 2025 (`manuals/iva/2025/source.pdf.extracted.md:5058-5059`).
- Confidence: high for `nacional`.
- Read in production: no. `iva_hint` has no reader (see "Readers").

### F07 No category states the 50 per cent IVA presumption for vehicles

- Categories and years: `vehiculo_combustible`, `vehiculo_mantenimiento`, `vehiculo_peaje`, `vehiculo_parking`; 2022 to 2026. `vehiculo_seguro` is exempt and correct.
- Current: `iva_hint = "general"` at `0064-categories-profile.toml:4239,4272,4305,4338,4378`, `:4411,4444,4477,4510,4550`, `:4755,4788,4821,4854,4894`, `:4927,4960,4993,5026,5066`. No IVA datum exists. `iva_mixed_use_share_for` returns `None` for them, so a MIXED row keeps its own share and a BUSINESS row deducts 100 per cent (`src/cadrumo/application/aggregation/iva_ledger.py:1728-1761`).
- Correct: cuotas on fuel, lubricants, parking, tolls, repair and renovation of the vehicle follow the vehicle. Turismos, remolques, ciclomotores, motocicletas, vehiculos mixtos and todo terreno are presumed 50 per cent affected. Six listed uses are presumed 100 per cent. The taxpayer may prove a higher degree, and the administration a lower one.
- Source: LIVA art. 95.Tres.2 to 4 and 95.Cuatro (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2271-2291`); Manual practico IVA 2025 (`src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md:5017-5035`).
- Confidence: high on the statute. The datum vocabulary `degree_of_use` / `not_deductible` cannot express a 50 per cent default; the ADR must settle the shape.
- Read in production: the missing datum is read as "none" (above).

### F08 MIXED rows of every other category deduct IVA by row share; LIVA denies it

- Categories and years: all categories without an `iva_mixed_use_share`; 2022 to 2026. That is every category except `suministros_home_office_*`, `telefonia_fija` and `telefonia_movil`.
- Current: the IVA ledger applies the `business_pct` of the row to the cuota (`iva_ledger.py:1728-1761`, caller `src/cadrumo/application/aggregation/_iva_transaction.py:466`).
- Correct: goods and services used at the same time for the activity and for private needs are not affected "directa y exclusivamente", and their cuota is not deductible (LIVA art. 95.Uno and Dos.2). Three exceptions give a share: bienes de inversion (95.Tres.1, by foreseeable use), vehicles and their accessories (F07), and suministros of an immovable partly affected (TEAC criterion read through the Manual, recorded in `2026-10-27-profile-field-remap-iva-home-office-suministros-research`). Goods under 3,005.06 EUR are not bienes de inversion (LIVA art. 108.Dos.5; registry fact `src/cadrumo/_data/registry/aeat/facts/0032-iva-bien-inversion-escaso-valor-threshold.toml:19`).
- Treatment each category needs for a MIXED row, from the statute:
  - Not deductible: `material_oficina`, `software_suscripcion`, `asesoria_fiscal`, `asesoria_juridica`, `asesoria_contable`, `publicidad_marketing`, `formacion_profesional`, `subcontratacion`, `suministros_cliente_directos`, `viajes_transporte`, `viajes_alojamiento`.
  - Degree of use: `arrendamiento_local` (lease of a bien de inversion), `suministros_local_afecto` (suministros of an immovable used for both), `reparaciones_conservacion` (follows the repaired good, 95.Cuatro.4).
  - Degree of use above 3,005.06 EUR, not deductible below: `hardware_amortizable`, `mobiliario_amortizable`.
  - Presumed 50 per cent: the four vehicle categories (F07).
  - Restaurants and travel (`manutencion_dietas_*`, `viajes_*`): also bound by LIVA art. 96.Uno.6 (F06).
- Source: LIVA art. 95.Uno, Dos.2, Tres.1 (`ley-37-1992.html.extracted.md:2264-2272`); art. 108.Dos.5 (`ley-37-1992.html.extracted.md:2487`); Manual practico IVA 2025 (`manuals/iva/2025/source.pdf.extracted.md:4991-4992,5036-5047`).
- Confidence: high on the statute; medium on mapping a MIXED row to "simultaneous use", because a MIXED row could stand for a split invoice that should be two rows.
- Read in production: yes, as the row-share fallback.

### F09 Confirmed items from the S11 list

- `arrendamiento_vivienda_afecto` has `iva_hint = "exempt_or_non_subject"` (`0064-categories-profile.toml:735,849,882,915,955`). It is wrong. LIVA art. 20.Uno.23.b exempts only buildings "destinados exclusivamente a viviendas" (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-20.html.extracted.md:143`). A dwelling used partly as an office is taxed. The correct hint is `general`. The AEAT page and DGT V0291-20 are in research stem `2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research`. Confidence: high. Read: no.
- `telefonia_movil` still has `iva_hint = "general"` (`:2728,2792,2856,2920,2988`) although `iva_mixed_use_share = "not_deductible"` landed. LIVA art. 95.Dos.2 (`ley-37-1992.html.extracted.md:2267`) and the Manual practico IVA 2025 (`manuals/iva/2025/source.pdf.extracted.md:4991-4992`) deny the deduction for simultaneous use. The correct hint is `non_deductible_input`. Confidence: high. Read: no.
- 34 `manual_renta` citations stay `source_not_bundled` (F10). The suministros and `telefonia_fija` ones are now verified.
- The es notes of the suministros and of `telefonia_fija` now state the 30 per cent rule and the IVA rule. The wrong rule number remains elsewhere (F14).

### F10 Thirty-four 2025 Manual de Renta citations are wrongly `source_not_bundled`, and their locators are not manual headings

- Categories and years: the 2025 variant of `cuotas_colegiales`, `cuotas_autonomos_ss`, `mutualidad_alternativa`, `arrendamiento_local`, `arrendamiento_vivienda_afecto`, `ibi_local_afecto`, `telefonia_movil`, `material_oficina`, `software_suscripcion`, `hardware_amortizable`, `mobiliario_amortizable`, `reparaciones_conservacion`, the five `vehiculo_*`, `asesoria_fiscal`, `asesoria_juridica`, `asesoria_contable`, `publicidad_marketing`, `formacion_profesional`, `viajes_transporte`, `viajes_alojamiento`, `seguros_responsabilidad_civil`, `seguros_salud_autonomo`, `gastos_bancarios`, `gastos_financieros`, `suministros_cliente_directos`, `subcontratacion`, `tributos_fiscalmente_deducibles`, `amortizacion_vivienda_afecto`, `ibi_vivienda_afecto`, `comunidad_vivienda_afecto`.
- Current: `citation.N.grounding = "source_not_bundled"` with a `grounding_reason` saying the manual is not in the corpus. The cited URL `.../ManualRenta2025Parte1_es_es.pdf` equals the `source_pdf_url` of the bundled manual (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/manifest.json`). Counted by script over the current file: 34 `manual_renta` and 2 `aeat_help` citations are `source_not_bundled`; 185 `ley_irpf`, 40 `reglamento_irpf` and 5 `manual_renta` are `verified`.
- Correct: the 34 manual citations are bundled and can be verified. The 2 `aeat_help` citations (`cuotas_autonomos_ss` and `mutualidad_alternativa`, "Cotizaciones al RETA") are accurately unbundled: no AEAT help page is in the corpus. Locators such as "Vehiculos y afectacion exclusiva" or "Vivienda parcialmente afecta - IBI" match no manual heading. Real locations in `manuals/renta/2025/part1/source.pdf.extracted.md`:
  - Criterios de afectacion, vehiculos, indivisibles: `:15759-15828`; titularidad against suministros: `:15842-15855`.
  - Seguridad Social y mutualidad del titular: `:17788-17949`; manutencion del titular: `:17956-17998`.
  - Servicios exteriores: arrendamientos `:18004`, reparaciones `:18135`, suministros `:18153-18200`, profesionales independientes `:18204`, primas de seguros and seguro de enfermedad `:18209-18232`, otros servicios exteriores `:18233-18241`.
  - Tributos `:18243-18291`; gastos financieros `:18295-18330`; amortizaciones `:18654`, tabla simplificada `:19136-19170`.
- The 2022 to 2024 variants carry statutory citations only, although the three earlier editions are bundled with the same statements (checked for F01, F02, F04 and F12). That is a gap, not an error.
- Confidence: high. Read in production: citations are copied into the Renta observation as `legal_references` (`ledger_expenses.py:629`).

### F11 `ibi_local_afecto` and `tributos_fiscalmente_deducibles` cite "art. 14 LIS por remision"

- Categories and years: `ibi_local_afecto`, `tributos_fiscalmente_deducibles`; 2022 to 2026.
- Current: `citation.0.locator = "art. 14 LIS por remision"` in the 2022 to 2024 and 2026 variants and `citation.1` in 2025 (`0064-categories-profile.toml:968-1139` and `:7828-7999`). The notes repeat it in all four locales (keys `ibi_local_afecto` and `tributos_fiscalmente_deducibles`: es `src/cadrumo/locales/es/common.yml:406-409,521-522`; en `src/cadrumo/locales/en/common.yml:380-383,495-496`; ca `src/cadrumo/locales/ca/common.yml:399-402,514-515`; hu `src/cadrumo/locales/hu/common.yml:384-387,501-502`).
- Correct: LIS art. 14 is "Provisiones y otros gastos" and says nothing about taxes. IBI and other non-state taxes are deductible under LIRPF art. 28.1, with LIS art. 15.b and 15.c excluding only the IS expense and sanctions. The Manual names IBI and IAE under "Otros tributos fiscalmente deducibles". Kind and hint are correct.
- Source: `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-14.html.extracted.md:1`; `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-15.html.extracted.md:5-6`; Manual practico Renta 2025 `manuals/renta/2025/part1/source.pdf.extracted.md:18285-18291`.
- Confidence: high.
- Read in production: citation yes (as F10); notes yes (LLM prompt, `llm.py:467-498`).

### F12 The mutualidad cap is right in the registry and wrong in every locale

- Categories and years: `mutualidad_alternativa`; 2022 to 2026.
- Current: the dated schedule is 14,057.40, 15,266.72, 16,030.82, 16,672.66 and 17,323.68 EUR (`0065-categories-statutory-cap.toml:23,44,65,86,106`). The notes state "limite legal de 15.000 EUR/ano por contribuyente" (key `mutualidad_alternativa`: es `src/cadrumo/locales/es/common.yml:441-445`; en `:415-419`; ca `:434-438`; hu `:419-423`).
- Correct: the limit is the cuota maxima por contingencias comunes of the RETA for each ejercicio, and only for the part that covers RETA contingencies. Each schedule value checks as base maxima x 12 x 28.30 per cent. 2022: 4,139.40 (Manual 2022 `manuals/renta/2022/part1/source.pdf.extracted.md:14757-14764`). 2023: 4,495.50 (`manuals/renta/2023/part1/source.pdf.extracted.md:17038-17046`). 2024: 4,720.50 (`manuals/renta/2024/part1/source.pdf.extracted.md:17709-17716`). 2025: 4,909.50 (`manuals/renta/2025/part1/source.pdf.extracted.md:17942-17949`). 2026: 5,101.20 under Orden PJC/297/2026 art. 18.1 and 18.2.a, giving 17,323.68 (read through the fetch tool summary of BOE-A-2026-7296; not read in full).
- The Manual 2024 contradicts itself: its novedades keep 15,266.72 (`manuals/renta/2024/part1/source.pdf.extracted.md:593-597`) while its detailed section computes 16,030.82. The registry follows the Orden and the detailed section. A verbatim quotation for 2024 must come from the detailed section.
- The citation locator "art. 30.2.1.a" is imprecise: the text is art. 30.2 regla 1.a, second paragraph, and has no letter a (`ley-35-2006.html.extracted.md:502-503`).
- Source: LIRPF art. 30.2 regla 1.a (`ley-35-2006.html.extracted.md:503`); Manual practico Renta 2025 `manuals/renta/2025/part1/source.pdf.extracted.md:17922-17949`.
- Confidence: high. Read in production: the schedule yes (`ledger_expenses.py:711-725`); the notes yes (LLM prompt).

### F13 The seguro de enfermedad note states a per-taxpayer cap and the wrong article

- Categories and years: `seguros_salud_autonomo`; 2022 to 2026.
- Current: notes say "500 EUR/ano por contribuyente (Ley 35/2006 art. 30.2.5.c, regla 1.a)" (key `seguros_salud_autonomo`: es `src/cadrumo/locales/es/common.yml:456-458`; en `:430-432`; ca `:449-451`; hu `:435-437`). The registry values are right: general 500 and discapacidad 1,500, per person per year (`0064-categories-profile.toml:6961` onward).
- Correct: 500 EUR for each insured person (the contribuyente, the cónyuge and the hijos menores de veinticinco años who live with him), or 1,500 EUR for each person with discapacidad. The article is 30.2 regla 5.a letra a. Regla 1.a concerns mutualidades.
- Source: `ley-35-2006.html.extracted.md:508-509`; Manual practico Renta 2025 `manuals/renta/2025/part1/source.pdf.extracted.md:18209-18232`.
- Confidence: high. Read in production: notes yes (LLM prompt); the Ratios pane does not list this category.

### F14 Notes cite "regla 4a" and "regla 2a" for rules that do not apply

- Categories and years: `amortizacion_vivienda_afecto` ("art. 30.2.5.b, regla 4a"), `ibi_vivienda_afecto` and `comunidad_vivienda_afecto` ("art. 30.2.5.b, regla 2a"); 2022 to 2026, all four locales. The en, ca and hu notes of `telefonia_fija` and the four `suministros_home_office_*` carried the same "regla 4a" until the S11 executor rewrote them (es first, the others later during the audit).
- Current, by key line: es `src/cadrumo/locales/es/common.yml:353-356,376-379,410-413`; en `src/cadrumo/locales/en/common.yml:327-330,350-353,384-387`; ca `src/cadrumo/locales/ca/common.yml:346-349,369-372,403-406`; hu `src/cadrumo/locales/hu/common.yml:330-333,353-356,388-391`.
- Correct: art. 30.2 regla 5.a letra b concerns suministros of the vivienda habitual only. Regla 2.a concerns family employment. Amortization, IBI and comunidad of a partly affected dwelling follow LIRPF art. 29.2 and RIRPF art. 22.3, with the area and ownership share (F05); the 30 per cent factor does not apply. The registry citations already say "art. 29.2 y art. 28.1"; only the notes are wrong.
- Source: `ley-35-2006.html.extracted.md:492,502-510`; Manual practico Renta 2025 `manuals/renta/2025/part1/source.pdf.extracted.md:15842-15855`.
- Confidence: high.
- Read in production: yes (LLM prompt; the Ratios pane for these usage-ratio categories).

### F15 The dietas label says "meals and stay" in en, ca and hu, and no note states the conditions

- Categories and years: `manutencion_dietas_nacional`, `manutencion_dietas_extranjero`; 2022 to 2026. The cap values (26.67, 53.34, 48.08 and 91.35 EUR per day) are correct.
- Current: labels `categories.registry.manutencion_nacional` and `manutencion_extranjero` read "(meals and stay)" (en `src/cadrumo/locales/en/common.yml:406-407`; ca `:425-426`; hu `:410-411`). The es label "Dietas de manutención" is right (`es/common.yml:432-433`). The notes in all four languages give only the amounts and the articles.
- Correct: the remission of LIRPF art. 30.2 regla 5.a letra c covers the quantitative limits for manutención only, not estancia. The deduction needs an expense of the contribuyente himself, incurred in the activity, in a hostelería or restauración establishment, paid by electronic means. The con-pernocta limit applies when the night is spent in a municipality other than the habitual workplace and the residence.
- Source: `ley-35-2006.html.extracted.md:511`; `rd-439-2007.html.extracted.md:321-324`; Manual practico Renta 2025 `manuals/renta/2025/part1/source.pdf.extracted.md:17956-17998`. No change of the four amounts was found: the bundled RIRPF carries an amendment note only for kilometraje (`rd-439-2007.html.extracted.md:317`), and a web search on 2026-10-27 found no 2026 amendment; a fetch of the BOE consolidated page was inconclusive.
- Confidence: high.
- Read in production: labels and notes yes.

### F16 Code behavior that changes the outcome of the cap and exclusive-use rules

These are not registry values. A correction of F01, F02, F12 and F13 needs them known.

- Annual caps are applied per row. `_evaluate_statutory_cap_rule` takes `min(deductible_basis, cap_applied)` for one transaction (`ledger_expenses.py:498-513`), and the annual and quarterly pipelines call it once per row (`src/cadrumo/application/aggregation/renta_ledger.py:997`, `src/cadrumo/application/aggregation/renta_gasto_ledger.py:581`). Several seguro or mutualidad rows that are each below the annual cap deduct above it together. Confidence: medium-high (read, not run).
- The dieta cap inputs are never supplied. `statutory_cap_days` and `statutory_cap_variant_id` have no producer outside the model (`ledger_expenses.py:88-89`; a grep of `src` finds none), so the daily and variant cap resolvers return `None` and every dietas row is refused as "missing statutory cap context" (`ledger_expenses.py:498-512,725-760`). Confidence: high.
- Exclusive use cannot be confirmed. `exclusive_use_confirmed` defaults to `False` and nothing sets it (`ledger_expenses.py:104,545`). Moving F01 and F02 to `requires_exclusive_use` makes those rows ineligible until a producer exists; the asset register already records a typed vehicle affectation declaration (`vehicle_affectation.py:84-125`). The move also removes the six categories from the user-ratio set, so the Ratios pane stops listing them and a persisted override becomes `not_eligible_override` (`ratios.py:182`). A MIXED row in a non-usage-ratio category is scaled by its share before the rule runs (`src/cadrumo/application/aggregation/_renta_business_eligibility.py:126`), so a MIXED vehicle row would still deduct a share unless the rule refuses it. Confidence: high.
- Every profile attribute enters the draft approval fingerprint (`src/cadrumo/application/filing/draft_review.py:792-800`, a `model_dump` of the whole profile). Any correction in this audit, including a citation or `iva_hint` edit, marks existing approved drafts stale with `category_profiles_changed`.

### Readers of each attribute in production

- `iva_hint`: unread. The only code that touches it builds the value (`src/cadrumo/domain/categories/registry.py:173-180`). It enters the approval fingerprint as hashed data only. Wrong values (F06, F09) mislead no calculation today.
- `proportionality_kind`, `statutory_multiplier`, `statutory_cap_*`, `statutory_cap_period`: read (`ledger_expenses.py:571-586,711-830`; `src/cadrumo/domain/usage_ratios/service.py:186`). No category uses `fixed_pct`, `non_deductible` or `requires_exclusive_use`, although the evaluator for the last exists (`ledger_expenses.py:539-552`).
- `notes` and `display_label`: read by the Ratios pane for usage-ratio categories only (`ratios.py:120-131`) and, for every category, by the LLM classifier hint, which sends the Spanish label, the kind and the first 120 characters of the note (`llm.py:467-498`).
- `citations`: read; copied to `legal_references` of each Renta result and observation (`ledger_expenses.py:629`).

### Categories checked and found correct

Kind, multiplier and caps are correct for every category not named above; the hint is correct unless named above.

- `cuotas_colegiales`: full; `exempt_or_non_subject` is right because LIVA art. 20.Uno.12 names the Colegios profesionales, on condition of no distortion of competition (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-20.html.extracted.md:55-57`).
- `cuotas_autonomos_ss`: full; not an IVA operation (Manual 2025 `:17788-17921`).
- `mutualidad_alternativa`: kind, cap schedule and hint (LIVA art. 20.Uno.16) correct; wording in F12.
- `arrendamiento_local`: full, `general` (a local de negocio is not exempt under art. 20.Uno.23.b).
- `ibi_local_afecto`, `tributos_fiscalmente_deducibles`: full, not subject; citation in F11.
- `suministros_local_afecto`: full, `general`; the note in all four locales is correct (30 per cent excluded for premises).
- `suministros_home_office_luz`, `_agua`, `_gas`, `_internet` and `telefonia_fija`: `usage_ratio_home_area` with multiplier 0.30 matches LIRPF art. 30.2.5.b (`ley-35-2006.html.extracted.md:510`), which names agua, gas, electricidad, telefonia e Internet. A proved share replaces the default ("superior o inferior"). The IVA share belongs to S11. The `telefonia_fija` IVA treatment rests on inference (low confidence; the ADR records it).
- `material_oficina`, `software_suscripcion`, `reparaciones_conservacion`, `asesoria_*`, `subcontratacion`, `suministros_cliente_directos`: full, `general`. IRPF follows LIRPF art. 28.1. IVA for a MIXED row is F08.
- `formacion_profesional`: full; `general` holds unless the provider is an authorized teaching entity (LIVA art. 20.Uno.9, `ley-37-1992-art-20.html.extracted.md:41`), as the earlier research records.
- `viajes_transporte`, `viajes_alojamiento`: full with no cap, correct because the 30.2 regla 5.a letra c remission excludes estancia (Manual 2025 `:17971-17980`); `general` is right (passenger transport and hostelería are taxed, LIVA art. 91.Uno.2.1 and 2.2, `ley-37-1992.html.extracted.md:2101-2102`) but the cuota follows LIVA art. 96.Uno.6.
- `seguros_responsabilidad_civil`, `vehiculo_seguro`, `seguros_salud_autonomo`: hint exempt (LIVA art. 20.Uno.16) is right. The seguro de salud caps are in F13.
- `gastos_bancarios`, `gastos_financieros`: full, exempt (LIVA art. 20.Uno.18). Bank fees for collection management, custody or POS rental are taxed, as the earlier research records. The financial-expense cap of LIS art. 16 (30 per cent of beneficio operativo, 1 million EUR floor, Manual 2025 `:18295-18330`) does not bind an autónomo below that floor.
- `amortizacion_vivienda_afecto`, `ibi_vivienda_afecto`, `comunidad_vivienda_afecto`: kind without multiplier and non-subject hints are right (the comunidad hint was not checked against a DGT text). Ownership share is F05, notes F14.
- `arrendamiento_vivienda_afecto`: kind right; hint F09.
- `manutencion_dietas_*`: the four amounts match RIRPF art. 9.A.3.a (`rd-439-2007.html.extracted.md:321-324`) and the Manual table (`manuals/renta/2025/part1/source.pdf.extracted.md:17990-17997`).
- Scopes `spending_category_catalogue`, `iva_deductibility_hint` and `proportionality_vocabulary`: internally consistent; not audited as law.

## Sources

- `src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:735,968-1139,2726-2988,3721-4032,4237-5297,6101-6240,6961-7122,7828-7999,8018-8588`
- `src/cadrumo/_data/registry/aeat/facts/0065-categories-statutory-cap.toml:23,44,65,86,106`
- `src/cadrumo/_data/registry/aeat/facts/0032-iva-bien-inversion-escaso-valor-threshold.toml:19`
- `src/cadrumo/_data/registry/aeat/facts/2025/mapping/0090-2025-modelo-100-first-slice-expense-routing-mapping.toml:133-134`
- `src/cadrumo/locales/es/common.yml:353-356,376-379,398-401,406-413,432-433,441-449,456-458,521-522`
- `src/cadrumo/locales/en/common.yml:327-353,380-387,406-407,415-419,430-432,495-496`
- `src/cadrumo/locales/ca/common.yml:346-372,399-406,425-426,434-438,449-451,514-515`
- `src/cadrumo/locales/hu/common.yml:330-356,384-391,410-411,419-423,435-437,501-502`
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:492,502-511`
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:317,321-324,473-477,544`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2101-2102,2264-2291,2301,2305,2487`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-20.html.extracted.md:41,55-57,143`
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-12-full.html.extracted.md:80-81,103-106,137`
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-14.html.extracted.md:1`
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-15.html.extracted.md:5-8`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:15759-15855,17788-17998,18004-18330,18654-18665,19136-19170,19442-19447`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/manifest.json`
- `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.md:593-597,15499,17709-17716,17925,18008`
- `src/cadrumo/_data/corpus/manuals/renta/2023/part1/source.pdf.extracted.md:14965,17038-17046,17260,17343`
- `src/cadrumo/_data/corpus/manuals/renta/2022/part1/source.pdf.extracted.md:12825-12830,14757-14764,14965-14969,15055`
- `src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md:4991-4992,5017-5047,5058-5059`
- `src/cadrumo/domain/renta/ledger_expenses.py:88-89,104,439-451,498-513,539-552,571-586,629,711-830`
- `src/cadrumo/domain/renta/actividad_asset/vehicle_affectation.py:1-10,84-125`
- `src/cadrumo/domain/usage_ratios/model.py:93`
- `src/cadrumo/domain/usage_ratios/service.py:186`
- `src/cadrumo/domain/categories/registry.py:173-180`
- `src/cadrumo/domain/transactions/llm.py:467-498`
- `src/cadrumo/application/ledger/ratios.py:120-131,182`
- `src/cadrumo/application/aggregation/renta_ledger.py:997`
- `src/cadrumo/application/aggregation/renta_gasto_ledger.py:581`
- `src/cadrumo/application/aggregation/_renta_business_eligibility.py:126`
- `src/cadrumo/application/aggregation/modelo_bindings_actividad_assets.py:135-197`
- `src/cadrumo/application/aggregation/iva_ledger.py:1728-1761`
- `src/cadrumo/application/aggregation/_iva_transaction.py:466`
- `src/cadrumo/application/filing/draft_review.py:792-800`
- Research stems `2026-10-27-profile-field-remap-iva-home-office-suministros-research` and `2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research`
- https://www.boe.es/buscar/act.php?id=BOE-A-2026-7296 (Orden PJC/297/2026, art. 18.1 and 18.2.a; retrieved 2026-10-27 through the fetch tool; first 100,000 of 169,072 characters read)
- Unverified, search summary only: no 2026 change of the RIRPF art. 9.A.3.a dieta amounts (web search 2026-10-27; BOE consolidated page fetch inconclusive)
