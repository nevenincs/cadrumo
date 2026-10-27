---
tags:
  - '#research'
  - '#profile-field-remap'
date: '2026-10-27'
modified: '2026-10-27'
body_schema: 'body-v2'
body_hash: 'sha256:a5332a51ca5735125d74bb59ccfe08f06c859b0a68f2c239ae248aad58a8d726'
related:
  - '[[2026-08-27-registry-dated-validity-frozen-constant-hunt-audit]]'
  - '[[2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research]]'
---

# `profile-field-remap` research: `IVA deductibility of home-office suministros`

Question (plan Step S11): how much input IVA may an autónomo deduct on suministros of a habitual dwelling partly used for the activity, and does the LIRPF art. 30.2.5ª.b factor of 30 per cent apply to IVA?

Conclusion: the 30 per cent factor does not apply to IVA. The deductible IVA share is the degree of use of the dwelling in the activity (grado de utilización), with no statutory multiplier. The basis is LIVA art. 95.Cuatro read with arts. 168 and 168 bis of Directive 2006/112/CE. It was fixed by the TEAC unified criterion RG 00/06654/2022 (19-07-2023), adopted by DGT replies V2657-23 and V0796-25, and applied by the Supreme Court in STS 976/2025. No source fixes a percentage or a calculation method. Floor area is the AEAT's own "reasonable criterion" for the dwelling, not a rule. The taxpayer must prove the share. Confidence: high that the 30 per cent factor is IRPF-only and that the share is proportional to use; medium that floor area is an acceptable default proxy; low for telefonía fija, which no source names.

Cadrumo today scales the IVA cuota by the same `business_pct` that carries the IRPF factor (raw afectación times 0.30). That deducts 30 per cent of the share the sources support, so the error runs against the taxpayer.

Not investigated: the DGT originals on the Hacienda site (read in third-party reproductions), the CENDOJ original of the STS (read in an AEDAF copy), DGT V2554-23 and V0257-21 beyond how V2657-23 and V0796-25 quote them, foral territories, special IVA regimes, cash accounting, and regularisation.

## Findings

### The 30 per cent factor is an IRPF rule and has no counterpart in IVA

- LIRPF art. 30.2.5ª.b makes the utilities "gasto deducible para la determinación del rendimiento neto en estimación directa" at "el porcentaje resultante de aplicar el 30 por ciento a la proporción existente entre los metros cuadrados de la vivienda destinados a la actividad respecto a su superficie total, salvo que se pruebe un porcentaje superior o inferior" (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:508-510`). The AEAT Manual de Renta 2025 repeats it as an IRPF special rule, with 40 m2 of 100 m2 giving 30% x 40% = 12% (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:18167-18203`).
- LIVA art. 95 contains no multiplier and no area rule (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2262-2291`). The BOE consolidated art. 95 has two versions only: 1993-01-01 and 1998-01-01 (Ley 66/1997, BOE-A-1997-28053). Retrieved 2026-10-27 from the BOE open-data API.
- No DGT reply, TEAC resolution or judgment read applies the IRPF factor to IVA. The only DGT position before 2023 was no deduction at all (V0257-21, 16-02-2021, as quoted in V2657-23 and V0796-25).

### The IVA basis is art. 95.Cuatro read with Directive arts. 168 and 168 bis

- Art. 95.Uno and Dos.2º deny deduction for goods and services used at the same time for the activity and for private needs (`ley-37-1992.html.extracted.md:2263-2267`). Art. 95.Tres admits partial deduction only for bienes de inversión, in the measure of foreseeable use (`:2271-2272`). Art. 95.Cuatro extends Tres to accessories, fuels, parking and tolls, and rehabilitation and repair (`:2286-2291`). Suministros are not on that list.
- TEAC RG 00/06654/2022, 19-07-2023, Sala Segunda, recurso extraordinario de alzada para unificación de criterio, qualified "Doctrina": art. 95.Cuatro, read in conformity with the Directive, is not a closed list and reaches suministros of immovable property, so the IVA on agua, luz and gas of property used for the activity and for private use is deductible in proportion to business use (https://serviciostelematicosext.hacienda.gob.es/TEAC/DYCTEA/criterio.aspx?id=00/06654/2022/00/0/1). Its support is Directive art. 168 bis, which requires deduction on immovable property used for business and private purposes "de manera proporcional a su utilización a efectos de las actividades de la empresa".
- The criterion text, as DGT V2657-23 quotes it: "cabe la deducción por el sujeto pasivo de las cuotas de IVA soportadas por los gastos de suministros (agua, luz, gas) a bienes inmuebles que formando parte del patrimonio de la empresa se utilicen tanto en las actividades empresariales como para uso privado. La deducción de dichas cuotas deberá efectuarse de manera proporcional a su utilización a efectos de las actividades de la empresa."
- The criterion binds the tax administration: LGT art. 242.4 (`src/cadrumo/_data/corpus/normatives/html/ley-58-2003.html.extracted.md:3056`).
- The AEAT Manual práctico IVA follows it. The sentence "La cuota soportada en los suministros será deducible en la parte en que el inmueble esté afecta a la actividad profesional" and a bullet citing the TEAC resolution first appear in the 2023 edition dated 26/09/2023 (`src/cadrumo/_data/corpus/manuals/iva/2023/source.pdf.extracted.md:5107` and `:5141-5145`). The 2024 and 2025 editions keep them (`manuals/iva/2024/source.pdf.extracted.md:5172` and `:5209-5213`; `manuals/iva/2025/source.pdf.extracted.md:5002` and `:5039-5043`). The 2022 edition has the dwelling example without the suministros sentence (`manuals/iva/2022/source.pdf.extracted.md:4813-4815`).

### DGT binding replies apply the criterion to the habitual dwelling of an autónomo

- V2657-23 (02-10-2023): an individual empresario affects part of the vivienda habitual. The cuotas on "el gasto de luz, agua o internet vinculado a su vivienda" are deductible "siempre que la misma se encuentre afecta parcialmente a su actividad empresarial o profesional" and "de forma proporcional a su utilización en dicha actividad económica". Suministros "destinados en exclusiva" to the activity are deductible in full. DGT says the change departs from V0257-21. Read at https://www.fiscal-impuestos.com/sites/fiscal-impuestos.com/files/NFC087469.pdf (reproduction of the DGT database, ref. NFC087469).
- V0796-25 (08-05-2025): same doctrine for a room "separada y diferenciada del resto de la vivienda". Luz and agua are deductible in proportion to use. Mobile telephony is not deductible in any amount because it is not "un gasto de un suministro de bienes inmuebles afectos parcialmente". DGT cites V2554-23 (25-09-2023) as the first statement of the change. Read at https://www.fiscal-impuestos.com/sites/fiscal-impuestos.com/files/V0796-2025.pdf.
- Neither reply names a metros cuadrados method or a percentage. Both say only "proporcional a su utilización".

### The Supreme Court ruling is STS 976/2025, not a ruling on art. 95.Tres.2ª

- Art. 95.Tres.2ª is the 50 per cent presumption for cars, trailers, mopeds and motorcycles (`ley-37-1992.html.extracted.md:2273`). It does not govern dwellings. Supreme Court judgments on it concern vehicles (STS 05-02-2018 rec. 102/2016 and STS 76/2019 were seen only in search summaries; unverified, not read). None bears on suministros.
- STS 976/2025, Sala Tercera Sección 2ª, 15-07-2025, rec. 5342/2023, ECLI:ES:TS:2025:3487, ponente González de Lara Mingo. Text read in the AEDAF copy (https://www.aedaf.es/es/documentos/descarga/74191/deduccion-en-el-iva-por-suministros-de-vivienda-compartida-con-el-despacho-profesional-la-distinta-apreciacion-de-los-hechos-por-los-organos-judiciale).
  - The doctrine fixed in FJ 4 is procedural: a court must explain a change in how it appraises the same facts.
  - FJ 5 decides the IVA merits by applying the TEAC criterion: "no se aprecian razones para no aplicar dicho criterio", fixing 50 per cent of the IVA on agua, luz and gas. The 50 per cent comes from the TSJ Andalucía finding of 10-02-2022 that the ground floor was about half of the habitable surface (FJ 2).
  - The dwelling belonged to the spouses, not to the company. The court applied the criterion anyway.
  - The court declined to review the invoices for fixed telephony, mobile telephony, alarm and household goods, because the lower court had found on the evidence that they were family expenses (FJ 5). It therefore grants nothing on fixed lines.
- The TEAC database entry for RG 00/06654/2022 notes that the Supreme Court applied the criterion in this judgment.

### The share is the degree of use; floor area is an endorsed proxy, not a rule

- The statute and the criterion say "proporcional a su utilización". No default percentage exists. The contrasts: the vehicle presumption of 50 per cent in art. 95.Tres.2ª, and the IRPF rule of 30% x area "salvo que se pruebe un porcentaje superior o inferior".
- The AEAT manual calls floor area "un criterio razonable" for the cuota on a dwelling that is also an office (`manuals/iva/2025/source.pdf.extracted.md:5039-5043`). It then says suministros are deductible "en la parte en que el inmueble esté afecta".
- The taxpayer in STS 976/2025 argued for the share "atendiendo a la superficie ocupada por el despacho y su horario de trabajo" (antecedente cuarto). A time factor is therefore a pleaded alternative; no source adopts it.
- Consequence: a share proved above or below the area ratio is lawful. The default proxy is office m2 over total m2, with no multiplier. This is an inference from the manual and the single judgment, not a stated rule.

### Conditions and evidence

- Afectación parcial is a question of fact. DGT cannot rule on it. The taxpayer must prove it. The proof "debe poder aportarse en el momento en que se pretenda ejercitar el derecho a la deducción", by any admissible means, freely and jointly appraised (V2657-23 section 4; LGT arts. 105.1 and 106, `ley-58-2003.html.extracted.md:1191-1198`; LEC art. 299).
- The affected part must be separable. The TSJ judgment quoted in STS 976/2025 FJ 2 speaks of "afectación parcial de un inmueble, con elementos divisibles y autónomos". The second TSJ judgment rejected a desk and a dining table photographed in the same room as proof.
- The activity must give right to deduct (LIVA art. 94.Uno, `ley-37-1992.html.extracted.md:2247-2249`). The general rules and the prorrata apply on top (`manuals/iva/2025/source.pdf.extracted.md:4964`). The share is multiplied by any prorrata ratio.
- The supplier invoice must be the original, complete, with the cuota stated separately (LIVA art. 97.Uno.1, Dos, Tres, `ley-37-1992.html.extracted.md:2315-2325`; manual `manuals/iva/2025/source.pdf.extracted.md:5074-5100`). RD 1619/2012 art. 6.1.c and e require the name and the address of the destinatario (`src/cadrumo/_data/corpus/normatives/html/rd-1619-2012.html.extracted.md:167,173`). For goods or services bought by several persons, each may deduct only if the invoice states the base and cuota of each separately (LIVA art. 97.Cuatro; manual `:5097`).
- "Invoice in the name of the taxpayer" is therefore an inference from art. 6.1.c and art. 97.Cuatro. I found no DGT, TEAC or judicial text on utility invoices issued to a spouse or co-owner. STS 976/2025 shows the practical risk: household invoices were treated as family expenses.
- The right is exercised in the period of accrual or later within four years (LIVA art. 99.Tres, `ley-37-1992.html.extracted.md:2350`).
- The TEAC wording says "que formando parte del patrimonio de la empresa". The Supreme Court applied it to property in the personal patrimony of the spouses. I did not find art. 95.Dos numbers 3 and 4 (not in the books, not in the business patrimony) addressed for suministros of the dwelling of an autónomo.

### Which categories are covered

- Luz, agua, gas: named by the TEAC criterion, V2657-23, V0796-25 and STS 976/2025.
- Internet: named only by V2657-23 ("luz, agua o internet vinculado a su vivienda"). The V0796-25 operative conclusion names luz and agua only.
- Telefonía fija: no source read names it. V0796-25 excludes mobile because it is not a supply to the property. A fixed line contracted for the dwelling fits that reasoning better, but that is inference.
- Telefonía móvil: no deduction for mixed use. The manual states it for a phone used for activity and private purposes at the same time (`manuals/iva/2025/source.pdf.extracted.md:4990-4991`), and V0796-25 repeats it.

### Dating

- Art. 95 has not changed since 1998-01-01. The TEAC criterion reads existing law, so it can support periods before 19-07-2023 that are still open. A secondary source (https://www.cuatrecasas.com/es/spain/fiscalidad/art/deducibilidad-iva-consumos-inmuebles-parcialmente-afectos) says so; I did not verify it against a primary text.
- The DGT applied the opposite administrative criterion until 25-09-2023 (V0257-21). The AEAT manual first states the new rule in the edition of 26/09/2023.
- The registry carries one variant per category per filing year from 2022 to 2026 (`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml`). Options for 2022 and 2023: apply the same share to every year; start at 2023-07-19 (TEAC) or 2023-09-26 (first manual edition with the sentence), which needs a finer date axis than a filing year; or mark earlier years advisory. The ADR must settle this.
- The doctrine rests on a reading of art. 95.Cuatro in conformity with the Directive. The TEAC itself records that the literal text of art. 95.Cuatro seems to refer only to vehicles (FJ 4, as quoted in V0796-25). A later reading by the Supreme Court in a judgment that fixes doctrine on the merits would be the stronger authority; STS 976/2025 fixes doctrine only on the procedural question.

### Code mapping

- The IVA ledger reads only the row. `business_proportionality_for` (`src/cadrumo/application/aggregation/iva_ledger.py:1715-1716`) calls `business_proportion` (`src/cadrumo/application/aggregation/business_proportion.py:28-47`): BUSINESS gives 1, MIXED gives `Transaction.business_pct`, anything else gives none. `src/cadrumo/application/aggregation/_iva_transaction.py:447` takes it as the proportion. Lines `:549-550` then set `iva_amount * proportionality` and `recargo_amount * proportionality`, and the cash-accounting path does the same at `:1164-1178`. The base stays unreduced. No category rule is consulted.
- `business_pct` is stamped at ledger add by `resolve_business_share_pct` (`src/cadrumo/application/ledger/ratios.py:376-430`, caller `src/cadrumo/application/ledger/ledger_add_command.py:163`). A share supplied by the operator wins (`ratios.py:415-419`), so a proved percentage can already be entered per row. Otherwise `censo_business_pct_for` (`ratios.py:297-330`) returns `effective_usage_ratio(rule, raw)`, which is raw afectación times `statutory_multiplier` (`src/cadrumo/domain/categories/proportionality.py:894-918`). `derive_home_office_ratios_from_censo` stores the same product for the Renta ratio store (`src/cadrumo/domain/usage_ratios/service.py:186`).
- Registry: `suministros_home_office_luz`, `_agua`, `_gas`, `_internet` and `telefonia_fija` each carry five yearly variants with `proportionality_kind = "usage_ratio_home_area"`, `statutory_multiplier = "0.30"` and `iva_hint = "general"` (`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:1349-1521`, `1526-1670`, `1703-1847`, `1880-2024`, `2229-2373`). Their citations are LIRPF art. 30.2.5.b and the Manual de Renta 2025. The latter is marked `source_not_bundled` although the manual is bundled at `manuals/renta/2025/part1`. `telefonia_movil` has `usage_ratio_personal`, no multiplier and `iva_hint = "general"` (`0064-categories-profile.toml:2057-2197`).
- `iva_hint` cannot carry a share. Its vocabulary is `general`, `exempt_or_non_subject`, `non_deductible_input`, described as "decoupled from the IVA taxonomy branch" (`0064-categories-profile.toml:824-825`). A search of `src` and `dev` found no reader of the `iva_hint` attribute beyond the constructor at `src/cadrumo/domain/categories/registry.py:174-180`.
- The citation vocabulary has `manual_iva` but no LIVA, TEAC or DGT source (`src/cadrumo/domain/categories/proportionality.py:79-98`). The legal catalogue already holds `ley-37-1992:art-95` (`src/cadrumo/_data/registry/aeat/legal/iva.toml:2482`). The Manual práctico IVA 2023, 2024 and 2025 are bundled. The TEAC resolution, the DGT replies and the STS are not.
- The Renta fold adds non-recoverable IVA to the IRPF base through the activity-wide `iva_deduction_ratio`, not through the row share (`src/cadrumo/application/aggregation/renta_gasto_ledger.py:482-484`; manual rule at `manuals/renta/2025/part1/source.pdf.extracted.md:18246-18255`). Changing the IVA share of a row therefore does not change Renta arithmetic.
- Renta already passes a MIXED row in a usage-ratio category through whole and applies the category rule once (`src/cadrumo/application/aggregation/_renta_business_eligibility.py:103`). Where that holds, `business_pct` on such a row feeds IVA only.
- Size of the error, 40 m2 of 100 m2, base 100.00, IVA 21.00: the sources give 40 per cent, a deductible cuota of 8.40. The code gives 0.40 x 0.30 = 12 per cent, a cuota of 2.52. The shortfall is 5.88, 70 per cent of the lawful figure. The earlier audit finding on `default_ratio` ran the other way, as an IRPF over-deduction (audit stem `2026-08-27-registry-dated-validity-frozen-constant-hunt-audit`).

### Where the registry can express the IVA share

- The share for these categories is: the degree of use, defaulting to raw afectación (`office_m2 / total_m2`, no multiplier), replaced by a proved percentage; 1 for a supply used only for the activity. It has a different legal source from the IRPF factor (doctrine on art. 95.Cuatro against LIRPF art. 30.2.5ª.b). The evidence therefore favors giving it its own registry datum on each variant, with its own citations, instead of reusing `statutory_multiplier`.
- Option A: an IVA-scoped field on `ProportionalityRule` (basis and multiplier) read by the IVA ledger through the category rule. It needs the raw afectación at IVA time, and the row does not carry it.
- Option B: for these families `censo_business_pct_for` returns raw afectación, so `business_pct` means degree of use and feeds IVA only. The multiplier then lives only in the Renta ratio store. It is the smaller change. It leaves the `statutory_multiplier` docstring and the censo-override warning to reconcile; the warning compares against the product (`ratios.py:433-478`).
- Either option needs citation sources for LIVA and for doctrine, or a bundled manual citation (`manual_iva`, 2023 edition onward). The ADR must settle the field shape, the citation vocabulary and the year treatment above.
- Adjacent: the Spanish note for the four `suministros_home_office_*` categories says "ratio por defecto 30%" and cites "regla 4ª" instead of rule 5ª (`src/cadrumo/locales/es/common.yml:471-488`). It states nothing about IVA. Plan Step S04 serves these notes in the Ratios pane.
- Adjacent: `arrendamiento_vivienda_afecto` carries a wrong `iva_hint`, already recorded in research stem `2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research`.

## Sources

- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:508-510`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2247-2291`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2315-2325`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2350`
- `src/cadrumo/_data/corpus/normatives/html/ley-58-2003.html.extracted.md:1191-1198`
- `src/cadrumo/_data/corpus/normatives/html/ley-58-2003.html.extracted.md:3056`
- `src/cadrumo/_data/corpus/normatives/html/rd-1619-2012.html.extracted.md:167,173`
- `src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md:4964,4990-4991,5002,5039-5043,5074-5100`
- `src/cadrumo/_data/corpus/manuals/iva/2024/source.pdf.extracted.md:5172,5209-5213`
- `src/cadrumo/_data/corpus/manuals/iva/2023/source.pdf.extracted.md:5107,5141-5145`
- `src/cadrumo/_data/corpus/manuals/iva/2022/source.pdf.extracted.md:4813-4815`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:18167-18203,18246-18255`
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/Manual_IVA_2025.pdf (origin of the bundled manual, per `manuals/iva/2025/source.pdf.extracted.json` attribution)
- https://serviciostelematicosext.hacienda.gob.es/TEAC/DYCTEA/criterio.aspx?id=00/06654/2022/00/0/1 (TEAC RG 00/06654/2022, 19-07-2023; retrieved 2026-10-27; fundamentos read as summarised by the fetch tool)
- https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-1992-28740/texto/bloque/a95 (LIVA art. 95 versions; retrieved 2026-10-27)
- https://www.fiscal-impuestos.com/sites/fiscal-impuestos.com/files/NFC087469.pdf (DGT V2657-23, 02-10-2023; third-party copy of the DGT database)
- https://www.fiscal-impuestos.com/sites/fiscal-impuestos.com/files/V0796-2025.pdf (DGT V0796-25, 08-05-2025; third-party copy of the DGT database)
- https://www.aedaf.es/es/documentos/descarga/74191/deduccion-en-el-iva-por-suministros-de-vivienda-compartida-con-el-despacho-profesional-la-distinta-apreciacion-de-los-hechos-por-los-organos-judiciale (STS 976/2025, 15-07-2025, rec. 5342/2023, ECLI:ES:TS:2025:3487; copy of the judgment text)
- https://www.cuatrecasas.com/es/spain/fiscalidad/art/deducibilidad-iva-consumos-inmuebles-parcialmente-afectos (secondary; TEAC facts and effect on open periods)
- `src/cadrumo/application/aggregation/iva_ledger.py:1715-1716`
- `src/cadrumo/application/aggregation/business_proportion.py:28-47`
- `src/cadrumo/application/aggregation/_iva_transaction.py:447,549-550,1164-1178`
- `src/cadrumo/application/aggregation/renta_gasto_ledger.py:482-484`
- `src/cadrumo/application/aggregation/_renta_business_eligibility.py:103`
- `src/cadrumo/application/ledger/ratios.py:297-330,376-430,433-478`
- `src/cadrumo/application/ledger/ledger_add_command.py:163`
- `src/cadrumo/domain/categories/proportionality.py:79-98,894-918`
- `src/cadrumo/domain/categories/registry.py:174-180`
- `src/cadrumo/domain/usage_ratios/service.py:186`
- `src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:824-825,1349-2373`
- `src/cadrumo/_data/registry/aeat/legal/iva.toml:2482`
- `src/cadrumo/locales/es/common.yml:471-488`
- Unverified (search summaries only, texts not read): STS 05-02-2018 rec. 102/2016 and STS 76/2019 on art. 95.Tres.2ª.
