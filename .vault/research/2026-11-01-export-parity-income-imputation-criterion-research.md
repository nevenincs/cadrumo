---
tags:
  - '#research'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-01'
body_schema: 'body-v2'
body_hash: 'sha256:3c8c8839ee3c765b407d4cc9a32d98e7bdeff68f6cdfec0b2589c53bd143170a'
related:
  - "[[2026-09-27-export-parity-renta-withholding-sources-research]]"
---
# `export-parity` research: `income imputation criterion`

Which ejercicio, and which Modelo 130 quarter, receives activity income and its withholding when an invoice accrues in one year and is paid in the next? This matters for two reasons. The accepted withholding-sources ADR keeps casilla 0599 advisory until the question is grounded, and the ledger keys every activity row by bank date today.

Primary text settles most of it:

- Accrual (devengo) is the legal default.
- Cash basis (cobros y pagos) is an election declared in the return. It is open only to taxpayers outside Código de Comercio accounting.
- Withholding is imputed to the same year as the income it comes from.
- TEAC unification doctrine adds a timing rule. The right to deduct a withholding arises only once the income is paid. If the accrual year was already filed, that year is rectified after payment.

Two points stay ambiguous and must stay advisory in the ADR: Modelo 130 inclusion of withholding paid after the quarter, and the year of transitional amounts when the criterion changes.

## Findings

### Accrual is the default for activity income

- LIRPF art. 14.1.b sends activity income to the Impuesto sobre Sociedades rules, "sin perjuicio de las especialidades que reglamentariamente puedan establecerse" (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:173-178`).
- LIS art. 11.1 imputes income and expense to the period of devengo "con independencia de la fecha de su pago o de su cobro" (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-11.html.extracted.md:3`). Art. 11.2 makes any other criterion depend on Administration approval.
- RIRPF art. 7.1 applies the LIS criteria "exclusivamente", subject only to art. 7.2 (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:290`).
- DGT V1177-25 (2025-07-01) reads LIS art. 11.1 as following "la corriente real de los bienes y servicios". It frames imputation as "devengo o cobros y pagos, si se hubiera optado o se optase por este último". In law, a taxpayer who never elected cash basis is on accrual.
- The bundled LIS art. 11 extract carries no official-source URL in its metadata (`ley-27-2014-art-11.html.extracted.json`, `attribution` field), whereas the RIRPF and LIRPF extracts cite BOE-A-2007-6820 and BOE-A-2006-20764. Its text matches the DGT's quotation in V1177-25.

### Accrual date for an issued invoice

- RD 1619/2012 art. 6.1.i requires the invoice to state the operation date, or the date an advance payment was received, only "siempre que se trate de una fecha distinta a la de expedición de la factura" (`src/cadrumo/_data/corpus/normatives/html/rd-1619-2012-art-6.html.extracted.md:24`). An invoice with no operation date therefore documents an operation on its issue date.
- The domain model carries `issued_at`, an optional `operation_date` and an `operation_date_role` (`src/cadrumo/domain/invoices/models.py:322-324`). The role tokens are `OPERATION_PERFORMED` and `ADVANCE_PAYMENT_RECEIVED` (`src/cadrumo/_data/registry/aeat/facts/0141-invoice-legal-classification-catalogue.toml:36-40`).
- An advance-payment date is not an accrual date. DGT V0486-14 (2014-02-21) covers a service paid in advance in December 2013 and performed from November 2013 to August 2014. Under accrual, the income and its withholding are imputed "proporcionalmente" as the service accrues. Under cash basis, both go to 2013. A multi-period service therefore needs an apportionment that the ledger does not model.

### Cash-basis election: who, how, how long

- RIRPF art. 7.2.1.º (`rd-439-2007.html.extracted.md:291-292`):
  - Who may elect: taxpayers whose bookkeeping falls under art. 68.3, 68.4, 68.5 or 68.6.
  - Scope: "para imputar temporalmente los ingresos y gastos de todas sus actividades económicas".
  - How: approved "por el solo hecho de así manifestarlo en la correspondiente declaración".
  - How long: "deberá mantenerse durante un plazo mínimo de tres años".
- Art. 7.2.2.º: the election loses effect if the taxpayer later falls under art. 68.2. Art. 7.2.3.º: it is unavailable to anyone who has an art. 68.2 activity or keeps Código de Comercio accounting (`:293-294`).
- RIRPF art. 68 (`rd-439-2007.html.extracted.md:1071-1087`) sets the bookkeeping categories:
  - 68.2: directa normal with a mercantile empresarial activity requires Código de Comercio accounting.
  - 68.3: a non-mercantile empresarial activity keeps record books only.
  - 68.4: directa simplificada.
  - 68.5: professionals under either modality of directa.
  - 68.6: objetiva.
- Eligibility therefore depends on three facts: the regime, whether an empresarial activity is mercantile, and whether Código de Comercio accounting is kept, obligatorily or voluntarily. The profile has `estimation_regime` (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:914-926`) and `activity_kind`, valued profesional or sectorial (`:932-937`). It has no fact for mercantile character or for the accounting kept. A professional on directa normal is eligible under 68.5. An empresarial taxpayer on directa normal is eligible only if the activity is non-mercantile (68.3).
- RIRPF art. 7.4 bars any change of criterion from leaving income or expense uncomputed or computed twice (`rd-439-2007.html.extracted.md:296`). It does not say which year receives the transitional amounts.
- Manual práctico de Renta 2025, parte 1, pp. 399-400 (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:16564-16605`):
  - It restates the election and the three-year minimum.
  - The election is shown with an "X" in casilla 0169 for estimación directa, 1443 for objetiva other than agricultural activities, and 1487 for agricultural, livestock and forestry activities in objetiva.
  - Taxpayers who elected in an earlier year and keep the election mark the same casillas again, so every return states the criterion.
  - For an entidad en atribución de rentas, the entity elects and all members must agree. The entity's election is independent of each member's own activities.
- AEAT's 2025 record dictionary places 0169 inside each `ActividadEstDirecta` element (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:270`). It places 1443 and 1487 inside the objetiva elements (`:333`, `:377`) and has an entity-level flag, 1576 (`:469`). The flag repeats per activity block, but the law makes the election cover all activities, so every block carries the same value.
- The registry models 0169, 1443 and 1487 as booleans with `semantic_role` `irpf_ed_cobros_pagos_flag`, `irpf_eo_cobros_pagos_flag` and `irpf_eo_agr_cobros_pagos_flag` (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:1240-1246`, `:9714-9720`, `:10045-10051`), inherited forward (`revisions/2021/revision.toml:693`, `revisions/2022/revision.toml:703`). Their `legal_refs` cite LIRPF arts. 27-32 and omit RIRPF art. 7, the provision that creates the option. No Python module reads any of the three casillas.

### Withholding follows its income

- RIRPF art. 78.1: the obligation to withhold arises "en el momento en que se satisfagan o abonen las rentas" (`rd-439-2007.html.extracted.md:1316`). Art. 79: the perceptor imputes withholding "al período en que se imputen las rentas sometidas a retención o ingreso a cuenta, con independencia del momento en que se hayan practicado" (`:1324`).
- DGT V1429-19 (2019-06-14): a professional on cash basis from 2018 rendered services in 2018 and collected them in 2019, and the clients withheld in 2018. Both the income and the withholding go to 2019.
- DGT V0486-14 states the general rule: withholding is imputed "siguiendo los criterios de imputación temporal que correspondan a los citados rendimientos".
- DGT V1177-25 restates that activity withholding goes to the same period as its income. Where the payer failed to withhold, the perceptor deducts the amount that should have been withheld (LIRPF art. 99.5, `ley-35-2006.html.extracted.md:2022`). The tax rules give the payer no claim against the perceptor for it.

### The right to deduct arises on payment (TEAC unification doctrine)

- TEAC resolución 00/03187/2011/00/00 of 27-09-2012, a recurso extraordinario de alzada para la unificación de criterio, calificación "Doctrina" (https://serviciostelematicosext.hacienda.gob.es/TEAC/DYCTEA/criterio.aspx?id=00/03187/2011/00/0/1).
- Facts: a professional on accrual deducted the withholding on 2007 invoices that had not all been collected. AEAT reduced the deduction for the uncollected ones.
- Criterion: withholding is imputed to the year of its income. No IRPF provision allows deducting withholding before the obligation to withhold arises, so the right to deduct arises "en el momento en que las rentas se abonen o satisfagan". LIRPF art. 99.5 still applies to income paid without the withholding due.
- Two cases follow:
  - Payment arrives before the accrual year's return is filed: that return includes both the income and the withholding.
  - The return was filed before payment: it includes only the income. Once payment arrives, the taxpayer rectifies that return to deduct the withholding.
- The criterion names rectification "en los términos del artículo 120.3 de la Ley 58/2003". For IRPF 2024 and later, that route is the autoliquidación rectificativa. The bundled LGT art. 120.3-4 provides for it (`src/cadrumo/_data/corpus/normatives/html/ley-58-2003-art-120.html.extracted.md:5-8`). Manual Renta 2025, parte 1, p. 65 (`manuals/renta/2025/part1/source.pdf.extracted.md:2615-2640`) makes it, from Orden HAC/242/2025, "la autoliquidación rectificativa como sistema único" for 2024 and later. The mechanism changed; the split between imputation year and deduction timing did not.
- A DYCTEA free-text search for "retenciones imputación cobro devengo" over 2012-01-01 to 2026-11-01 returned only this criterion. No later TEAC criterion overturning it was found.
- Answer to the question as posed: under accrual, a December invoice paid with withholding in January has its income and withholding in year N. The withholding becomes deductible in N only once the payment exists. If N was already filed, it is recovered by rectifying N, never by crediting it in N+1. It may not be credited before payment.

### Modelo 130 follows the same imputation, with an unsettled edge

- Modelo 130 instructions, apartado I (`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html:73-86`):
  - Income and expense are determined "atendiendo a las normas reguladoras de la modalidad ... del método de estimación directa", cumulatively from 1 January to the quarter end.
  - Casilla 06 is the withholding "soportados ... correspondientes al período".
- RIRPF art. 110.3.a allows deducting "las retenciones practicadas ... correspondientes al período de tiempo transcurrido desde el primer día del año hasta el último día del trimestre" (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-110.html.extracted.md`, apartado 3.a).
- DGT V3298-15 (2015-10-26): a professional's clients remit the withholding without paying the invoice. Inclusion in the 130 "vendrá determinada por la imputación en el mismo de los rendimientos de los que aquellas proceden". The quarterly payment therefore follows the elected criterion for both income and withholding.
- What stays unsettled:
  - The sources point in different directions. V3298-15 ties inclusion to imputation alone, while the TEAC criterion ties deductibility to payment and art. 110.3.a says "practicadas".
  - No primary text found decides the quarterly payment for a December accrual paid in January before the fourth-quarter 130 is filed, or for a withholding remitted on an unpaid invoice.
  - The two errors differ in consequence. Under-crediting a 130 only moves the credit to the annual return through 0604 and 0599. Over-crediting is a pago a cuenta error.

### Estimation regimes

- Under estimación objetiva, income comes from módulos. The cash-basis flag changes little there beyond volume-based activities and withholding timing.
- Modelo 131 deducts withholding "correspondientes al trimestre" (RIRPF art. 110.3.b). It is outside the 0599 and casilla 06 scope and was not investigated further.
- The 0169 flag belongs to estimación directa; objetiva uses 1443 and 1487.

### Current code keys activity income and withholding by bank date

- The cumulative Modelo 130 windows partition transactions by date (`src/cadrumo/application/aggregation/renta_income_ledger.py:300-320`). The Modelo 100 path partitions by the period's start and end (`:443`).
- Each row's filing date is `transaction.raw.value_date or transaction.raw.booked_date` (`:926-940`). This is the cash-basis criterion, applied to every taxpayer.
- The linked invoice's `operation_date` and `issued_at` are never consulted for dating. For an accrual taxpayer, a December invoice collected in January lands in N+1.
- Bank rows with no linked invoice have no accrual date at all.

### Prior-record check

- `2026-09-24-retenciones-workflow-modelo-123-count-authority-research` cites RIRPF arts. 94.1 and 108.1 for withholding timing (lines 26 and 47). For their scope, the citations are correct:
  - Art. 94.1 is the capital mobiliario rule, under which the obligation arises at exigibility or earlier payment (`rd-439-2007.html.extracted.md:1673-1676`).
  - Art. 108.1 is the payer's quarterly declaration (`:1848-1850`).
- The suspected mis-citation does not hold. The rule does not transfer to activity income, which art. 78.1 governs, and no edit is needed.

### Options the ADR must settle

- What an absent criterion fact means. Reading absence as accrual matches the legal default. Reading it as undeclared matches the profile schema's convention for operator facts ("absent means undeclared and must not be read as either value", `schema.toml:937`) and the payer-fact declaration-state ruling (`2026-09-23-calendar-obligations-payer-fact-declaration-state-adr`). The evidence favours undeclared, with accrual offered as the proposed answer, because a cash-basis election made in an earlier year cannot be seen from a fresh profile.
- Eligibility, given that no accounting fact exists.
- Whether the three-year minimum is enforced by a finding or a refusal.
- How unresolved accrual dates (no linked invoice, an advance payment) are graded.
- How accrued-but-unpaid withholding is surfaced.
- The Modelo 130 edge.
- The year of transitional amounts when the criterion changes.

### Not investigated

- Atribución de rentas entity elections (casilla 1576).
- Modelo 131 withholding timing.
- Operaciones a plazos (LIRPF art. 14.2.d, LIS art. 11.4).
- Apportionment of multi-period services.
- Foral territories.

## Sources

- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:173-178` (LIRPF art. 14), `:2022` (art. 99.5); official https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014-art-11.html.extracted.md:3` (LIS art. 11.1); the extract carries no source URL
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:288-296` (RIRPF art. 7), `:1071-1087` (art. 68), `:1314-1324` (arts. 78-79), `:1673-1676` (art. 94), `:1848-1850` (art. 108); official https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-110.html.extracted.md` (RIRPF art. 110)
- `src/cadrumo/_data/corpus/normatives/html/rd-1619-2012-art-6.html.extracted.md:24` (RD 1619/2012 art. 6.1.i)
- `src/cadrumo/_data/corpus/normatives/html/ley-58-2003-art-120.html.extracted.md:5-8` (LGT art. 120.3-4)
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:16564-16605` (pp. 399-400), `:2615-2640` (p. 65)
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html:73-86`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:270`, `:333`, `:377`, `:469`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:1240-1246`, `:9714-9720`, `:10045-10051`
- `src/cadrumo/_data/registry/aeat/facts/0141-invoice-legal-classification-catalogue.toml:36-40`
- `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:914-937`
- `src/cadrumo/domain/invoices/models.py:322-324`
- `src/cadrumo/application/aggregation/renta_income_ledger.py:300-320`, `:443`, `:926-940`
- DGT V1429-19, V0486-14, V1177-25 and V3298-15, primary text read 2026-11-01 at https://petete.tributos.hacienda.gob.es/consultas/?num_consulta=V1429-19 (substitute each number)
- TEAC 00/03187/2011/00/00 of 27-09-2012, primary text read 2026-11-01 at https://serviciostelematicosext.hacienda.gob.es/TEAC/DYCTEA/criterio.aspx?id=00/03187/2011/00/0/1
- Unverified: no claim above rests on a search snippet. The absence of later TEAC doctrine rests on a single DYCTEA query.
