---
tags:
  - '#research'
  - '#export-parity'
date: '2026-11-01'
modified: '2026-11-01'
body_schema: 'body-v2'
body_hash: 'sha256:0001acc9729361901001f45e25a22a8a06f39132c2acc2dfca2e5d53409ab6c1'
related:
  - "[[2026-11-01-export-parity-income-imputation-criterion-adr]]"
  - "[[2026-11-01-export-parity-suffered-withholding-schemas-adr]]"
---

# `export-parity` research: `Withholding legal readings`

The operator ruled that five withholding questions left open by `2026-11-01-export-parity-income-imputation-criterion-adr` and `2026-11-01-export-parity-suffered-withholding-schemas-adr` are regulated questions, to be answered from the norms rather than chosen. This record answers each one from primary text: BOE consolidated law, AEAT instructions and manuals, binding DGT consultas read on petete, and TEAC unification doctrine read on DYCTEA. It builds on `2026-11-01-export-parity-income-imputation-criterion-research` and does not restate it. For each question it gives the rule, its locators, how certain the rule is, and the rule as code would implement it.

Certainty levels used below:

- **Explicit text:** a norm states the rule.
- **Binding doctrine:** a DGT consulta vinculante (LGT art. 89.1) or a TEAC unification criterion states it.
- **Reasoned inference:** the rule follows from explicit text, but no norm or doctrine states it.
- **Unaddressed:** no primary text found decides it, and a conservative treatment is proposed and labelled as such.

Summary of the answers:

- **Modelo 130 casilla 06.** Withholding goes into the cumulative window its income is imputed to (binding, DGT V3298-15), and it may be deducted only once the income is paid (TEAC). Payment after the quarter end but before the 130 is filed is permitted by the text but not addressed by any authority. Withholding on unpaid income is excluded.
- **Change of criterion.** Amounts that would otherwise go uncomputed are imputed to the first ejercicio of the new criterion (binding, DGT V2024-16 and V4636-16).
- **Partial payment.** Each payment carries its own withholding: the rate times the gross income that payment satisfies (explicit text). Each payment's withholding becomes deductible when that payment is made, in the accrual year (inference from TEAC). How a partial payment divides between IVA and the base is unaddressed.
- **Three-year minimum.** The first ejercicio the cash basis applies counts as year one. This is inferred from the text and the DGT's counting of the parallel three-year renuncia terms.
- **Repercutido ingreso a cuenta.** The full ingreso a cuenta is credited whether or not it is repercutido; repercusión only removes it from the income (explicit text, plus DGT V1974-21 for the base). In Modelo 100, casilla 0007 = 0004 + 0005 − 0006, and casilla 0596 carries the full 0005.

## Findings

### Q1. Modelo 130 casilla 06 follows imputation, and each withholding is deductible only once its income is paid

**Rule.**

- Casilla 06 holds the withholding and ingresos a cuenta "correspondientes" to the cumulative period from 1 January to the quarter end. Which period a withholding corresponds to is decided by the imputation of the income it comes from (RIRPF arts. 79 and 110.3.a; DGT V3298-15).
- Each withholding is deductible only once it has been "practicada", which happens when the income is paid (RIRPF art. 78.1; TEAC 00/03187/2011).

Primary text:

- RIRPF art. 110.3.a lets a professional in estimación directa deduct "las retenciones practicadas y los ingresos a cuenta efectuados correspondientes al período de tiempo transcurrido desde el primer día del año hasta el último día del trimestre" (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md:1903`; also `rd-439-2007-art-110.html.extracted.md`, apartado 3.a). The same applies to urban rental as an activity (3.a.2.º) and to image rights (3.a.3.º).
  - Estimación objetiva and agricultural activities instead use withholding "correspondientes al trimestre" (110.3.b), which is Modelo 130 casilla 10 and Modelo 131.
- Modelo 130 instructions, casilla 06: "Suma de las retenciones e ingresos a cuenta soportados ... correspondientes al período comprendido entre el primer día del año y el último día del trimestre" (`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html:86`). All data are cumulative from 1 January (`:73`).
- RIRPF art. 109.1 makes the 130 a pago a cuenta, and art. 109.2 exempts professionals with at least 70 per cent of the prior year's income subject to withholding (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-109.html.extracted.md`).
- RIRPF art. 79: withholding is imputed "al período en que se imputen las rentas ..., con independencia del momento en que se hayan practicado" (`rd-439-2007.html.extracted.md:1324`). Art. 78.1: the obligation to withhold arises "en el momento en que se satisfagan o abonen las rentas" (`:1316`).

Doctrine:

- DGT V3298-15 (26-10-2015, vinculante). A professional's clients sometimes pay the withholding to the Treasury without paying the invoice. The DGT does not answer that case directly. It holds that "la inclusión de las retenciones en el modelo 130 ... vendrá determinada por la imputación en el mismo de los rendimientos de los que aquellas proceden". The quarterly window therefore follows the taxpayer's criterion, art. 7.2 cash basis or accrual.
- DGT V4965-16 (15-11-2016, vinculante). An architect on accrual included 2015 fees in his 130s, while the paying university's Modelo 190 for 2015 reported only the amount paid and the withholding on it. The fees go to 2015, the year they accrued, and so does the withholding "detraído" from them. This confirms that the payer's 190 year (the payment year) can legitimately differ from the perceptor's imputation year.
- TEAC 00/03187/2011, unification criterion, already summarised in the earlier research. No provision allows deducting withholding before the obligation to withhold arises. The right to deduct therefore arises when the income is paid, and an earlier return already filed is rectified.

The two edge cases:

- **Withholding on income imputed to the window, paid after the quarter end but before the 130 is filed.** No primary text excludes it.
  - Art. 110.3.a asks only that the withholding be "practicada" and "correspondiente" to the period. V3298-15 reads "correspondiente" as imputation. The TEAC reading of "practicada" is met once the payment exists, and the payment exists before the 130 is filed.
  - Certainty: reasoned inference from explicit text. No DGT or TEAC text addresses the quarterly case directly.
  - Limiting inclusion to payments on or before the window end is lawful, because no rule obliges a perceptor to deduct the earliest possible credit. The cost is small. The 130 is cumulative, so the next quarter's casilla 06 picks the amount up, since its window still contains the imputation and the payment now exists. After the fourth quarter, Modelo 100 casilla 0599 absorbs it.
- **Withholding on income imputed to the window but not yet paid.** It is excluded: the TEAC criterion makes no deduction possible before the income is satisfied. Certainty: binding doctrine, applied by inference to the pago fraccionado.
  - The V3298-15 facts, where the payer remitted the withholding but did not pay the invoice, remain unaddressed. V3298-15 answers by imputation alone. The TEAC criterion ties deductibility to payment of the income. Whether the remittance alone makes the withholding "practicada" is not decided in any source read.
  - Conservative treatment (labelled): exclude it from casilla 06 and raise an advisory finding naming the invoice. The structure favours this because over-deducting a pago a cuenta understates the amount due, while under-deducting only defers the credit to 0599.

**Implementable rule.**

- Inputs per withholding item:
  - the taxpayer's criterion (`devengo` or cobros y pagos) for the ejercicio;
  - the income's imputation date: accrual date under devengo, payment date under cobros y pagos;
  - the payment date and paid gross amount;
  - the withholding practised on that payment;
  - the 130 window `[1 Jan, quarter end]`;
  - optionally, the date the 130 was actually filed.
- Casilla 06 is the sum of the withholding whose imputation date falls in the window and whose payment exists at the cut-off.
  - Floor cut-off, always lawful: the window end.
  - Permitted cut-off: the 130 filing date, used only when the filing date is a recorded fact.
- Unpaid imputed withholding is excluded from casilla 06 and reported as a non-blocking finding with its count and amount.
- The withholding-remitted-but-income-unpaid case is excluded, with an advisory finding.
- The fourth-quarter reconciliation against 0599 tolerates exactly the itemised withholding imputed to the year but paid after the cut-off.

### Q2. Amounts a change of criterion would leave uncomputed go to the first ejercicio of the new criterion

**Rule.** RIRPF art. 7.4 forbids a change of criterion from leaving income or expense uncomputed or computing it twice (`rd-439-2007.html.extracted.md:296`). The DGT imputes the amounts that would otherwise be left uncomputed to the ejercicio in which the change takes effect.

- DGT V2024-16 (11-05-2016, vinculante; normativa LIRPF art. 14.1.b, RIRPF art. 7).
  - Facts: a taxpayer on cash basis for five years changes to accrual in 2014. Invoices issued in 2013 and collected in 2014 were computed in neither year.
  - Answer: "las rentas obtenidas deberán imputarse siempre una única vez". Because 2014 brings a change of criterion and those amounts "no se han imputado anteriormente", they "deberán imputarse en este período impositivo [2014], pues no puede quedarse sin imputar ninguna renta obtenida".
- DGT V4636-16 (02-11-2016, vinculante; normativa LIRPF art. 14).
  - Facts: a lawyer on cash basis for more than three years moves to accrual in 2016, with fees for services up to 2011 still uncollected.
  - Answer: under art. 7.4 the change "llevaría a la imputación en el ejercicio 2016 de los rendimientos correspondientes a los ejercicios 2011 y anteriores que no se hubieran imputado por la aplicación del criterio de cobros y pagos". They are not time-barred.
- Certainty: binding doctrine, consistent across two consultas, for the cash-to-accrual direction.
- LIS art. 11.3 does not answer this. Its rule concerns accounting entries booked in the wrong period and charges to reserves from accounting-criterion changes (`src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md:110-112`). RIS (RD 634/2015) art. 1 governs approval of non-accrual criteria (`rd-634-2015.html.extracted.md:51`). Neither contains a "primer período impositivo del nuevo criterio" rule. The year comes from DGT doctrine applying RIRPF art. 7.4, not from a reglamentary text.

The other direction, accrual to cash basis:

- Art. 7.4 forbids imputing anything "nuevamente". Income and expense accrued and computed in the last accrual year are not computed again when they are collected or paid under the new cash basis.
- Certainty: explicit text. No consulta for this direction was found.

Withholding on transitional amounts:

- By art. 79 the withholding follows its income. On a cash-to-accrual change it goes to the change year, deductible once paid (TEAC).
- On an accrual-to-cash change, withholding on income already computed in the accrual year belongs to that year, even if it is collected after the change. If that year was already filed, it is recovered by rectifying it.
- Certainty: reasoned inference from arts. 7.4 and 79 and the TEAC criterion.

Modelo 130 quarter for transitional amounts in the change year: unaddressed.

- The pago fraccionado base is the net income "correspondiente al período ... desde el primer día del año" (RIRPF 110.1.a). The transitional amounts are attributed to the year without a date inside it.
- Conservative treatment (labelled):
  - transitional income and expense enter the change year's first-quarter window, so the cumulative pagos fraccionados are not understated;
  - transitional withholding enters each window only once paid, as in Q1;
  - each item carries an advisory finding marking it as transitional.

**Implementable rule.**

- Inputs: the criterion per ejercicio, and per income or expense row its accrual date and payment date.
- On a change from cobros y pagos in year N−1 to devengo in year N:
  - Every row accrued before 1 January N and paid on or after 1 January N, which no year has computed, is imputed to N, together with its withholding.
  - The row is tagged `transitional_criterion_change` and reported as a non-blocking finding listing the rows.
  - Rows accrued and paid before N were computed under cobros y pagos and are not recomputed.
- On a change from devengo in N−1 to cobros y pagos in N:
  - Rows accrued in or before N−1 and paid in N are excluded from N, since they were already computed in N−1.
  - Their withholding stays in N−1. If N−1 is filed, a rectification finding is raised.
  - Rows paid in N for income accrued in N are computed in N.
- Duplicate check: a row computed in more than one ejercicio, or in none, across a criterion change blocks.

### Q3. Each partial payment carries its own withholding, deductible once that payment is made

**Rule.**

- Activity withholding is the rate applied "sobre los ingresos íntegros satisfechos": RIRPF art. 95.1 for professionals at 15 or 7 per cent (`rd-439-2007.html.extracted.md:1685`), and art. 101.1-2 for image rights and art. 75.2.b income (`:1808-1810`).
- The obligation arises "en el momento en que se satisfagan o abonen las rentas" (art. 78.1, `:1316`).
- A partial payment is therefore its own withholding event. The withholding equals the rate times the gross income that payment satisfies. The perceptor computes the income at "la contraprestación íntegra devengada" (LIRPF art. 99.5, `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md:2022`).
- Certainty: explicit text.

Which portion is creditable, and when:

- All of the income and all of its withholding are imputed to the income's imputation year (art. 79).
- The withholding on each paid portion becomes deductible when that portion is paid (TEAC 00/03187/2011). The withholding on the unpaid remainder is not deductible until it is paid. If the imputation year's return is filed first, each later payment's withholding is recovered by rectifying that year.
- Certainty: reasoned inference applying binding doctrine per payment. The TEAC criterion was stated per invoice, but its reasoning turns on the act of payment, and art. 78.1 attaches the obligation to each payment.

Payer shortfall:

- Where a payer, by its own exclusive fault, withholds less than is due on a payment, the perceptor deducts the amount that should have been withheld (LIRPF art. 99.5, second paragraph, `:2023`).
- Payments of legally fixed public-sector remuneration are an exception: only the amount actually withheld is deductible (`:2024`).
- Certainty: explicit text.

Unaddressed: how a partial cash receipt divides between IVA, the IRPF base and the withholding.

- No source read sets an allocation rule for a payment smaller than the invoice total.
- Conservative treatment (labelled):
  - Take the gross amount satisfied, and the withholding practised, from the payer's own statement where one exists: the remittance or the certificate under RIRPF art. 108.3.
  - Otherwise allocate pro rata to the invoice's net payable, so that paid share = cash received ÷ (base + IVA − withholding), and keep the result advisory with a finding.
  - Never infer a withholding larger than the rate times the allocated gross.
- Advance payments before accrual are the separate apportionment case covered by DGT V0486-14 in the earlier research.

**Implementable rule.**

- Inputs per payment: the linked invoice (base, IVA, rate), the payment date, the cash received, and optionally the payer-declared gross amount and withholding.
- `expected_withholding = rate × gross_satisfied`, at two-decimal money.
- The payment's creditable withholding is the payer-declared amount where present. It is raised to the expected amount only under the art. 99.5 shortfall rule, which needs an explicit operator assertion that the payer is at fault. A mismatch is reported as a finding.
- The item is imputed to the invoice's imputation year and deductible from its payment date onward. It feeds the Q1 rule for casilla 06 and 0599 per payment, not per invoice.
- A pro-rata allocation without a payer statement stays advisory.

### Q4. The first ejercicio of the cash basis counts as year one of the three-year minimum

**Rule.** RIRPF art. 7.2.1.º deems the option approved "por el solo hecho de así manifestarlo en la correspondiente declaración" and requires it to be kept "durante un plazo mínimo de tres años" (`rd-439-2007.html.extracted.md:292`). The return that manifests the option is the return of the ejercicio to which the criterion applies. The Manual Renta 2025 has the flag marked in every year's return (earlier research). The three years are therefore the ejercicios in which the criterion applies, counting from the first one. A cash basis first applied to ejercicio N binds N, N+1 and N+2, and N+3 is the first ejercicio that can return to accrual.

Supporting doctrine on the parallel RIRPF three-year terms:

- The renuncia to estimación objetiva "tendrá efectos para un período mínimo de tres años" (art. 33.3, `:589`). The renuncia to directa simplificada has the same term (art. 28, `:534`).
  - DGT V0173-18 (29-01-2018): a renuncia filed in December 2014 took effect for 2015, 2016 and 2017, so it could be revoked for 2018.
  - DGT V1316-20 (08-05-2020): a renuncia made at registration in 2017 meant the minimum had not elapsed in 2019 but had for 2020. The registration year is year one.
- DGT V1616-26 (17-06-2026), on the "tres años siguientes" of an exclusion: an exclusion effective for 2025 binds "2025, 2026 y 2027".
- DGT V4636-16 counts the cash basis itself by years of application ("aplicado durante cuatro años. Es decir, al menos en los ejercicios 2012, 2013, 2014 y 2015").

Certainty: reasoned inference from explicit text, supported by consistent DGT counting of the analogous three-year terms. No consulta or TEAC text on art. 7.2 counting was found.

Exception: art. 7.2.2.º ends the option early if the taxpayer becomes subject to art. 68.2 bookkeeping. Certainty: explicit text, already in the earlier research.

**Implementable rule.**

- Inputs: the criterion per ejercicio, the first ejercicio of the current cobros y pagos run, and per year the art. 68.2 or Código de Comercio accounting fact.
- A change to devengo in year Y is in conflict when `Y − first_cash_year < 3`, unless the art. 7.2.2.º loss of effect applies in Y.
- A change that does not move from cobros y pagos to devengo starts no count.
- A conflict is a finding against the declared criterion. It does not rewrite the stored fact.

### Q5. A repercutido ingreso a cuenta is credited in full, and repercusión only removes it from the income

**Rule.**

- LIRPF art. 99.6: "Cuando exista obligación de ingresar a cuenta, se presumirá que dicho ingreso ha sido efectuado. El contribuyente incluirá en la base imponible la valoración de la retribución en especie ... y el ingreso a cuenta, salvo que le hubiera sido repercutido" (`ley-35-2006.html.extracted.md:2026`).
- LIRPF art. 43.2 repeats the valuation rule: "A dicho valor se adicionará el ingreso a cuenta, salvo que su importe hubiera sido repercutido al perceptor" (`:790`).
- LIRPF art. 79.e deducts "los ingresos a cuenta" from the cuota líquida without any repercusión condition (`:1494-1500`), and art. 99.1 counts ingresos a cuenta as pagos a cuenta (`:2010-2013`).
- Repercusión therefore changes the income only, and the credit is the full ingreso a cuenta, whether or not repercutido. When it is repercutido, the perceptor has borne it economically, so it is not added to the income. Certainty: explicit text read together.
- DGT V1974-21 (23-06-2021, vinculante) confirms the base side with a worked example: valuation 10, ingreso a cuenta at 20 per cent = 2, and an unrepercutido ingreso a cuenta gives a rendimiento íntegro en especie of 12.
- DGT V1122-11 (04-05-2011) confirms that the payer's 190 and certificate report the valuation without the ingreso a cuenta, and carry separate "ingresos a cuenta efectuados" and "ingresos a cuenta repercutidos" fields.
- Manual Renta 2025: "Rendimiento íntegro = Valoración + Ingreso a cuenta no repercutido" for work income (`src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:9010`, p. 210; worked example `:9090-9110`, pp. 212-213). The same formula applies to capital mobiliario (`:14974`) and to activity income (`:24026-24028`).

How the ingreso a cuenta is valued:

- Work income: rate times the art. 43.1 valuation (RIRPF art. 102.1, `rd-439-2007.html.extracted.md:1818`).
- Capital mobiliario: rate times acquisition cost or cost to the payer plus 20 per cent (art. 103.1, `:1823`).
- Activity income: rate times market value (art. 104, `:1830`).
- The valuation itself never includes the ingreso a cuenta.

Casilla effect in Modelo 100 for ejercicio 2025:

- From the record dictionary (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:104-107`):
  - 0004 Valoración;
  - 0005 Ingresos a cuenta;
  - 0006 Ing. a cuenta repercutidos;
  - 0007 Importe íntegro = [0004] + [0005] − [0006].
- The credit is 0596 "Por rendimientos del trabajo" (`:959`), within 0609 (`:973`), and carries the full 0005.
- Prizes in kind use the same pattern: 0285 and 0295 are the repercutidos casillas (`:549`, `:560`).
- Activity income in kind has no separate casilla. Its valuation plus any unrepercutido ingreso a cuenta enters ingresos íntegros (manual `:24026-24028`), and the ingreso a cuenta is credited through 0599.
- The registry models 0004 to 0007 with the matching roles (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:25-50`).

**Implementable rule.**

- Inputs per in-kind item:
  - `valoracion_especie`, under the art. 43.1, 103 or 104 rule;
  - `ingreso_a_cuenta`, the amount the payer had to make, presumed made under 99.6;
  - `ingreso_a_cuenta_repercutido`, at most `ingreso_a_cuenta`.
- Income = valoración + ingreso_a_cuenta − repercutido (0007 for work income).
- Credit = retención + ingreso_a_cuenta, in full (0596 for work income, 0599 for activity income).
- Repercutido above ingreso_a_cuenta is refused.

### Contradictions with existing decision records

- `2026-11-01-export-parity-income-imputation-criterion-adr`:
  - Item 8 and "Open questions" treat the year receiving transitional amounts as an open legal reading. DGT V2024-16 and V4636-16 settle it for the cash-to-accrual direction (Q2), and art. 7.4 settles the reverse.
  - Item 3 treats the three-year count as open. The evidence supports counting the first ejercicio as year one (Q4), which is the stricter count the ADR already applies pending a ruling.
  - Item 6 keeps partial-payment withholding advisory. Q3 shows the per-payment rule is explicit, and only the IVA and base allocation of a partial receipt without a payer statement remains unaddressed.
  - Item 7 counts casilla 06 withholding "paid on or before the window end". That is the lawful floor, not a requirement of the norm. The text also permits payments up to the 130 filing date (Q1). The research behind the ADR describes the edge as unsettled; this record narrows it.
- `2026-11-01-export-parity-suffered-withholding-schemas-adr`:
  - Its proposed reading that repercusión does not reduce the credit agrees with LIRPF arts. 79.e and 99.6 (Q5). Its schema constraint that repercutido may not exceed ingreso a cuenta agrees with casilla 0007.
  - It compares cross-checks by exact Decimal equality, including `datos_fiscales { income_class }`. For an accrual taxpayer, the payer's Modelo 190 and datos fiscales report withholding in the payment year (DGT V4965-16 facts), so 0599 can legitimately differ by the withholding on income accrued in one year and paid in another. This is an observation to verify when P06.S09 declares that cross-check, not an established defect.

### Not investigated

- Allocation of the withholding base when an invoice carries IVA and other surcharges, beyond the pro-rata hypothesis above.
- Modelo 131 and casilla 10 timing (RIRPF 110.3.b, "correspondientes al trimestre").
- Atribución de rentas.
- Foral territories.
- TEAC doctrine on the 130 edge, searched only through the existing criterion.
- The DGT searches used petete's free-text, cuestión and hechos fields. Consultas phrased differently may exist.

## Sources

- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007.html.extracted.md`, RIRPF:
  - `:288-296` art. 7;
  - `:534` art. 28;
  - `:589` art. 33.3;
  - `:607` art. 34.3;
  - `:1211` art. 75;
  - `:1314-1324` arts. 78-79;
  - `:1683-1685` art. 95;
  - `:1806-1830` arts. 101-104;
  - `:1884` art. 109;
  - `:1892-1903` art. 110.
  - Official text: https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820
- `src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-109.html.extracted.md` and `rd-439-2007-art-110.html.extracted.md`
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006.html.extracted.md`, LIRPF:
  - `:173-178` art. 14;
  - `:790` art. 43.2;
  - `:1494-1500` art. 79;
  - `:2008-2027` art. 99.
  - Official text: https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764
- `src/cadrumo/_data/corpus/normatives/html/ley-27-2014.html.extracted.md:106-115` (LIS art. 11); official text https://www.boe.es/buscar/act.php?id=BOE-A-2014-12328
- `src/cadrumo/_data/corpus/normatives/html/rd-634-2015.html.extracted.md:51` (RIS art. 1)
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html:73`, `:86`, `:96`
- `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md`:
  - `:8995-9010` (p. 210);
  - `:9090-9110` (pp. 212-213);
  - `:14965-14974`;
  - `:24026-24028`;
  - `:54437-54444` (p. 1378).
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:104-107`, `:549`, `:560`, `:959-973`
- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:25-50`
- DGT consultas vinculantes, full text read 2026-11-01 on https://petete.tributos.hacienda.gob.es/consultas/ (search by "Nº de consulta"):
  - V3298-15 (26-10-2015);
  - V4965-16 (15-11-2016);
  - V2024-16 (11-05-2016);
  - V4636-16 (02-11-2016);
  - V0173-18 (29-01-2018);
  - V1316-20 (08-05-2020);
  - V1616-26 (17-06-2026);
  - V1974-21 (23-06-2021);
  - V1122-11 (04-05-2011).
- TEAC 00/03187/2011/00/00 of 27-09-2012, unification criterion, read 2026-11-01 at https://serviciostelematicosext.hacienda.gob.es/TEAC/DYCTEA/criterio.aspx?id=00/03187/2011/00/0/1
- No claim rests on a commercial summary or a search snippet. The "no doctrine found" statements rest only on the petete queries named above.
