---
tags:
  - '#research'
  - '#export-parity'
date: '2026-09-27'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:25947060c6989486c834e739ca75f1e4215b5a5e1c26501f5ce28c3a7fb75e2e'
related: []
---
# `export-parity` research: `renta withholding sources`

Question: where must Cadrumo's Modelo 100 (IRPF annual return) take the withholding (retenciones, ingresos a cuenta) and the payments on account (pagos fraccionados) that the taxpayer SUFFERED, including a taxpayer who is at once an employee, an autonomo invoicing Spanish business clients, and a withholding agent for others. It matters because casillas 0592 to 0606 are subtracted from the cuota (casilla 0609 feeds 0610), so a wrong source directly misstates the amount payable or refundable.

Conclusion of the evidence: the law and every Renta design from 2022 to 2025 treat these casillas as credits of the perceptor, evidenced by the payer's certificate and reported to AEAT through the payer's informative returns (190, 180, 193 and others), plus the taxpayer's own self-assessed Modelo 130 and 131 payments. The live registry instead binds 0596 and 0597 to the declarant's own payer-side returns (111, 123, and from 2024 and 2025 also 193 and 190), leaves 0599 unbound although the ledger already derives the professional withholding suffered on issued invoices, has no source for datos fiscales, and lets a borrador value silently outrank a lower-precedence value. The option space for correcting this is framed at the end; the choice belongs to the ADR.

## Findings

### Law: only suffered withholding and self-assessed payments are credits in the perceptor's return

- LIRPF art. 79.e subtracts from the cuota liquida the retenciones, ingresos a cuenta and pagos fraccionados provided for by the Law and its regulation (BOE-A-2006-20764, art. 79; also `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-79.html.extracted.md`).
- LIRPF art. 99.1 defines the three kinds of payment on account. Art. 99.2 makes entities, and also individual taxpayers who carry on economic activities, withholding agents for income they pay in that activity, withholding "on account of the perceptor's" IRPF. An autonomo can therefore be both perceptor and payer in the same year.
- LIRPF art. 99.5: the perceptor computes the full gross consideration; where withholding was not made, or was short, for a cause attributable exclusively to the payer, the perceptor still deducts what ought to have been withheld; for statutory public-sector salaries only the amount actually withheld is deductible; where the gross cannot be proven, the Administration may gross up the net amount received. Art. 99.7 obliges activity taxpayers to self-assess pagos fraccionados.
- LIRPF art. 105.1 and RIRPF art. 108.1 to 108.3: the payer files periodic returns (quarterly or monthly) and an annual summary, and must give the perceptor a certificate of the withholding practised before the Renta filing period opens. RIRPF art. 108.4: the payer communicates the percentage applied when paying, except for activity income, where the perceptor's own invoice usually states it (BOE-A-2007-6820).
- RIRPF arts. 74 to 76: who withholds (art. 76.1.b includes activity taxpayers paying income in their activity) and which income is subject (art. 75: trabajo, capital mobiliario, professional and certain agricultural or forestal activities, urban rentals, art. 75.2.b income, prizes). RIRPF art. 95.1 fixes the professional rate at 15 per cent, and 7 per cent in the start year and the two following years, and for listed activities (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-95.html.extracted.md`).
- RIRPF art. 109.2 exempts a professional from pagos fraccionados when at least 70 per cent of the prior year's activity income bore withholding; art. 110.3.a deducts the professional withholding suffered year-to-date inside each Modelo 130 (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-109.html.extracted.md`, `rd-439-2007-art-110.html.extracted.md`).

Consequence: an amount the declarant withheld from an employee, a professional, a landlord or a capital-income recipient is that recipient's credit and the declarant's debt already paid over to the Treasury. It never reduces the declarant's own cuota. For the payer it reaches the Renta only as part of the gross deductible expense of the activity.

### The Renta casillas and what the official designs expect, 2022 to 2025

The record-design dictionaries keep the same numbering in all four years (2022 lines 893-907, 2023 lines 912-926, 2024 lines 932-946, 2025 lines 959-973 of the dictionaries under `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/`):

| Casilla | XML field | Meaning (paraphrased) | Evidence the manual names |
| --- | --- | --- | --- |
| 0596 | RET1 | withholding on rendimientos del trabajo | payer certificate |
| 0597 | RET2 | withholding on capital mobiliario | payer certificate |
| 0598 | RET3 | withholding on urban rentals, whether or not an activity | payer certificate; the per-property field 0153 (C_RET) sums into a same-numbered InmueblesRes total (2025 dictionary lines 261 and 265) |
| 0599 | RET4 | withholding on activity income other than urban rentals | payer certificate |
| 0592, 0593, 0594, 0600 | RET5A-D | withholding attributed by an entidad en atribucion de rentas, fed from 1597-1600 | entity's attribution |
| 0601 | RET6 | withholding imputed by an AIE or UTE (from 0264) | entity's imputation |
| 0602 | RET7 | ingresos a cuenta of LIRPF art. 92.8 (image rights) | payer |
| 0603 | RET8 | withholding on capital gains, prizes included | payer certificate |
| 0604 | RET9 | pagos fraccionados ingresados (economic activities) | the taxpayer's own Modelo 130 or 131 |
| 0605 | RET10 | IRNR quotas of a taxpayer who became resident | IRNR withholding and quotas |
| 0606 | RET11 | withholding under Directive 2003/48/CE accrued before 2019 | foreign payer |
| 0609 | PAGOS | total of 0592 + 0593 + 0594 + 0596 to 0606 | derived |

The Renta manual carries the same text in each year (2022 lines 62321-62343, page 1609; 2023 lines 71507-71536, pages 1849-1850; 2024 lines 58475-58504, pages 1490-1491; 2025 lines 54444-54468, page 1378, all under `src/cadrumo/_data/corpus/manuals/renta/<year>/part1/source.pdf.extracted.md`). It lists the income classes that can carry withholding (trabajo; capital mobiliario; urban rentals whether or not an activity; activity income except urban rentals; atribucion; AIE and UTE imputations; image-rights imputations; capital gains including prizes and subscription rights), restates the payer's duty to certify under RIRPF art. 108.3, and says activity taxpayers deduct the pagos fraccionados for the year as recorded in the Modelo 130 or 131 they filed. Casilla numbering and source expectations did not change across the four designs; no year-specific divergence was found for these casillas.

### What AEAT prefills, and its standing

- The borrador and the datos fiscales are built from economic data third parties report in informative returns, plus the personal information AEAT holds. The taxpayer may modify or complete them, and failing to obtain them does not relieve the filing obligation (2025 manual, pages 35-37, lines 1272-1276, 1380-1386 and 1438-1445; https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c01-campana-declaracion-renta/borrador-declaracion-irpf/obtencion-borrador-declaracion-irpf-datos-fiscales.html). The 2025 manual states that taxpayers with any kind of income, economic activities included, may obtain the borrador, although LIRPF art. 98 itself describes the borrador as informative only and lists narrower sources that a ministerial order can extend (BOE-A-2006-20764, art. 98).
- The third-party returns that carry the suffered amounts are other people's filings keyed to the taxpayer's NIF: Modelo 190 recipient records (for example clave A for employees and clave G for professional activities, with subclaves distinguishing the 15 per cent general rate, the 7 per cent start rate and other rates; `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_190/files/01-190-orden-eha-3127-2009-de-10-de-noviembre-actualizada-por-orden-hac-1431-2025-de-3-de-dicie.pdf.extracted.md:592` and the subclave list after line 965), Modelo 180 for rentals and Modelo 193 for capital mobiliario. The taxpayer's own 111, 115, 123, 180, 190 or 193 filings record what the taxpayer withheld from others. They are never the source of the taxpayer's own credits.
- The operator's assumption is therefore right that AEAT prefills withholding reported by paying companies and the taxpayer's filed pagos fraccionados. That prefill is informative rather than conclusive: a payer can fail to file or file late, and the borrador's figure can differ from the certificate, so it is a strong cross-check rather than a filing-grade authority by itself. Not investigated: the exact per-concept layout of the datos fiscales download, which has no copy in the in-repo corpus.

### The live registry conflates payer-side returns with suffered withholding

I verified the per-revision wiring by compiling the authored registry with `dev.registry.compiler.authority.compile_structural_authority`, a typed structural compile with no publication, over revisions 2020 to 2025:

- 0596 is bound to `renta-modelo-111-retenciones-periodicas` in every revision. That binding sums the declarant's own Modelo 111 casilla 28 over every quarterly and monthly period (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml:4134`, `.../2020/bindings/0001-declarations.toml:24`). The Modelo 111 instructions define casilla 28 as the sum of all withholding the filer practised under every heading (`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_111/files/modelo-111-instrucciones.html`, "Casilla 28"). In 2024 a manual certificate binding, `renta-certificado-trabajo-retenciones`, is added as an alternate (`.../2024/bindings/0001-declarations.toml:257`, `.../2024/revision.toml:2370`). In 2025 the declarant's own Modelo 190 total, `renta-modelo-190-retenciones-anuales`, is added as a further alternate (`.../2025/bindings/0001-declarations.toml:14`, `.../2025/revision.toml:2408`).
- 0597 is bound to the declarant's own Modelo 123 (`.../2020/bindings/0001-declarations.toml:37`, with the source casilla switched to 09 at `.../2024/revision.toml:8545`). From 2024 the declarant's own Modelo 193 total is an alternate (`.../2024/bindings/0001-declarations.toml:2`, `.../2024/revision.toml:2374`).
- 0598 is manual in 2020 to 2023 and from 2024 a copy of 0153 (`.../2024/formulas/0001-declarations.toml:82`). That is correct for capital inmobiliario. Whether RET3 must also carry withholding on urban rentals run as an economic activity, which the manual includes, is not yet grounded against the dictionary and remains an open item.
- 0599 is manual and deliberately unbound, with an authored comment saying the application holds no data for it (`.../2020/casillas/0001-declarations.toml:4156-4175`). The ledger does hold such data; see the next section.
- 0604 is computed from the declarant's own Modelo 130 casilla 19 and Modelo 131 casilla 15 (`.../2020/formulas/0001-declarations.toml:2612`, `.../2020/bindings/0001-declarations.toml:49` and `:61`). That is the correct source family. Casilla 19 of Modelo 130 is a signed per-quarter result, and a negative quarter or a complementaria changes what a plain sum measures (`src/cadrumo/_data/corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html`, "Casilla 19"). Whether the sum equals "pagos fraccionados ingresados" in those cases is not proven by the fold-in test and needs its own grounding.
- In 2025, 1577 (net income attributed by an entidad en atribucion) is bound to a relation that sums `tipo2.renta-atribuible-importe` of a Modelo 184 (`.../2025/bindings/0001-declarations.toml:2`). The 184 is the entity's filing. The binding is correct only if the store holds exactly this member's record.
- `aeat_prefilled = true`, the flag that admits borrador values, sits on the Modelo 111 binding (`.../2020/bindings/0001-declarations.toml:31`) and, from 2025, on the tax-residence profile binding (`.../2025/revision.toml:10668`). The AEAT-prefill tier for 0596 is therefore keyed to the payer-side binding identity.
- The C3 fix marks 111, 123, 193, 190 and 184 as `taxpayer_files_source = false` (`.../2020/dependency_classifications/0001-declarations.toml:2-16`, `.../2024/dependency_classifications/0001-declarations.toml:18-24`, `.../2025/dependency_classifications/0001-declarations.toml:2-26`). That scopes the clean-state gate but does not stop a value flowing when the taxpayer does file those returns as a payer.
- Alternate bindings are defined as reviewed equivalent sources of one factual amount, and disagreeing values are refused before calculation (`src/cadrumo/domain/calculations/registry/schema_surfaces.py:348`, `src/cadrumo/domain/calculations/registry/bindings.py:292-320`). The declarant's 111 total, the declarant's 190 total and the declarant's salary certificate are not equivalent facts.

Effect by persona:

- An employee who files no payer returns gets 0596 only from the manual certificate binding. The verification advisory `implies_nonzero(["0012", "0596"])` flags a missing value (`.../2020/verification_predicates/0001-declarations.toml:28-31`).
- An employee who is also a payer and files Modelo 111 gets, without a certificate, an 0596 equal to the tax withheld from other people. That overstates the credit and understates tax. With a certificate whose total differs, the calculation is refused as a conflict between equivalent bindings. The only correct configuration, the certificate alone, cannot be reached while the 111 relation resolves.
- In 2025 the same holds for the declarant's own Modelo 190, and from 2024 for 0597 with the declarant's own Modelo 123 and 193.

The live-path test the former source file asserts that four filed Modelo 111 quarters fold into 0596, which enshrines the conflation. The registry's own advisory comments state the opposite, correct semantic: 0596 is the withholding the taxpayer suffered, which the payer declares (`.../2020/verification_predicates/0001-declarations.toml:1-27`).

### What the ledger holds for suffered withholding

- Issued invoices carry `retention_rate` and `retention_amount`, validated for sign, as a fraction, against the base and against the rate (`src/cadrumo/domain/invoices/models.py:370-371`, `:715-776`).
- Each activity income observation carries `withheld_amount` and a `withheld_derivation` marker (`src/cadrumo/application/aggregation/renta_income_ledger.py:155-156`, `:971-978`). The figure declared on the linked sales invoice is used first. Otherwise it is inferred as invoice gross minus cash received, capped by the registry's maximum supported rate. "No substrate" and "refused above the supported rate" are kept distinct from a real zero (`src/cadrumo/application/aggregation/_renta_income_evidence.py:164-217`, `src/cadrumo/core/aggregation.py:652`).
- Modelo 130 casilla 06 already consumes this quantity through `modelo-130-actividad-economica-retenciones-cumulative` with fact `withheld_amount_sum` (`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-declarations.toml:123-157`). The provider's `target_casilla_id` is an observation match key, so the value reaches casilla 06 only through an application redirect driven by a governed route (`src/cadrumo/application/aggregation/modelo_bindings.py:804`, `src/cadrumo/domain/renta/retenciones_routing_integrity.py:28-77`).
- No Modelo 100 binding reads `withheld_amount_sum`. The unrouted-quantity screen (`src/cadrumo/domain/calculations/registry/ledger_renta_income_bindings.py:473-524`, wired at `src/cadrumo/application/aggregation/modelo_bindings.py:641`) therefore reports the suffered professional withholding as unrouted for every Modelo 100 revision from 2020 to 2025. I confirmed this against the structurally compiled revisions with a synthetic 150.00 withholding row. The credit surfaces as an advisory and never reaches 0599.
- Employment rows (IRPF category `trabajo`, purpose `employment_income`, not a net-paid invoice: `src/cadrumo/_data/registry/aeat/facts/0081-irpf-ledger-category-taxonomy.toml:33-35`) record only the net bank credit, with no gross amount and no withholding. They are excluded from activity income (`src/cadrumo/application/modelo/_art109_activity_income.py:328`). No payroll or certificate model exists, so 0596 cannot come from the ledger.
- Rent categories are expense-side only (`0081-irpf-ledger-category-taxonomy.toml:25-31`), which is the taxpayer as tenant and payer. The ledger holds no suffered rental or capital withholding.
- The payer-side withholding stores (`src/cadrumo/domain/calculations/registry/retenciones_bindings.py:209`, `src/cadrumo/domain/calculations/registry/withholding_bindings.py:526`) hold what the declarant withheld from others. They feed 111, 115, 180, 190 and 193 and must stay out of 0592 to 0606.
- The income-tax acceptance oracle already computes the activity withholding (`dev/acceptance/income_tax/scenario.py:282`). The CLI journey's Modelo 100 expectation omits 0599 and passes `renta-certificado-trabajo-retenciones=0` (`dev/acceptance/income_tax/cli_journey.py:459-486`).
- Temporal caveat, not yet grounded: withholding arises when income is paid, while activity income is imputed on accrual. An invoice issued in one year and paid in the next needs its own grounding before a ledger fold is filing-grade.

### Live pull and how a prefilled value competes

- No datos fiscales pull exists. The Renta Web borrador portal entry is link metadata only (`src/cadrumo/domain/portals/_entries/portal_renta_web_borrador.py`).
- `aeat app live borrador 100 import --file` parses a local borrador PDF (`src/cadrumo/entrypoints/cli/_app_live_borrador_cli.py:46-120`) through the registry's `borrador_pdf` profile. That profile targets only 0505, 0545, 0546, 0585 and 0586 (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2021/extraction_profiles/0001-declarations.toml:109-120`), and the values are stored under `casilla.<id>` keys (`_app_live_borrador_cli.py:105`).
- The calculation tier (`--borrador` on `aeat app modelo work calculate`) admits only snapshot keys equal to `aeat_prefilled` binding ids and refuses anything else as forbidden (`src/cadrumo/application/modelo/borrador_binding.py:185-195`, `:440-441`). Reading the code, an imported PDF snapshot cannot feed a calculation. This was not exercised, because this worktree has no published authority.
- The borrador provenance rows carry no terminal origin (`borrador_binding.py:249`), and the terminal-origin vocabulary has no class for third-party AEAT data or a payer certificate (`src/cadrumo/domain/calculations/registry/binding_terminal_origin.py:44-76`).
- The precedence order is profile, then the backend mesh, then borrador, then caller (`src/cadrumo/application/modelo/calculation_resolution.py:173-175`). The overlay silently keeps the later tier's value (`src/cadrumo/application/aggregation/source_resolution_operations.py:184-188`). The precedence test replaces a backend value of 1.00 with a borrador value of 125.50 and asserts no disagreement finding (`src/cadrumo/entrypoints/tests/profile_persistence/test_borrador_binding.py:282-335`). A prefilled value can therefore silently win over a ledger or relation value, which the no-silent-under-declaration contract forbids for filing-bound fields.
- The live filed-data pull captures the declarant's own filed declarations from the Sede register (`src/cadrumo/application/live/filed_data.py:1-15`). It can corroborate 0604 through the taxpayer's own 130 and 131 filings. It cannot supply suffered withholding.

### Routing in the mixed case

| Amount | Belongs in | Must never reach |
| --- | --- | --- |
| IRPF withheld by the employer from the nomina (employer's 111 and 190 clave A) | 0596, evidenced by the employer certificate, cross-checked with datos fiscales | 0599; any value derived from the declarant's own 111 or 190 |
| 15 or 7 per cent withheld by a business client from the autonomo's invoice (client's 111 and 190 clave G) | 0599, from the issued-invoice withholding and the client certificate, cross-checked with datos fiscales and the fourth-quarter Modelo 130 casilla 06 | 0596; 0604 |
| Modelo 130 or 131 amounts the autonomo paid | 0604, from the taxpayer's own filed 130 and 131, corroborated by the live filed-declaration pull or justificantes | 0599 (the 130 already nets the withholding in casilla 06, so adding casilla 06 to 0604 would count it twice) |
| Withholding the declarant practised on employees, professionals or a landlord (declarant's own 111, 115, 190, 180) | nowhere among the credits; the gross salary or rent paid is a deductible activity expense | 0592 to 0606 |
| Capital withholding the declarant practised as a payer (declarant's own 123, 193) | nowhere among the credits | 0597 |
| Withholding a business tenant practised on the declarant's rent (tenant's 115 and 180) | 0153 per property, then 0598 | 0599 |
| Bank withholding on interest or dividends (bank's 193, 196 and similar) | 0597 | any payer-side fold |

The fourth-quarter 130 casilla 06 cross-check is independent only when the filed 130 is an immutable prior filing. Recomputing it from the same ledger as 0599 checks consistency, not correctness. Independent evidence comes from the payer's certificate or the payer-reported datos fiscales.

### Registry shape options under the delta-keyed standard

- Option A, manual only: one `manual_input` binding per credit casilla, with the payer-side bindings removed. This is the smallest change. It keeps the ledger's 0599 figure advisory and provides no typed per-payer evidence.
- Option B, a typed suffered-withholding evidence family: an encrypted per-payer record (payer NIF, income class mapped to casilla by `semantic_role`, gross amount, withholding, ingreso a cuenta, period, evidence fingerprint), with one resolver at its own defining module and one aggregation per income class. The ledger's `withheld_amount_sum` feeds 0599 directly as a bound casilla, with no redirect like Modelo 130's. Borrador or datos fiscales values enter as a cross-check with a visible divergence finding. This matches `aeat-registry-bindings` and `sensitive-financial-data-secure-storage-only`, and costs a new source kind and store.
- Option C, AEAT prefill as the primary source: this needs a datos fiscales import that does not exist yet. The prefill is informative in law, and the taxpayer remains responsible for it.

Delta implications for any option: declare the corrected binding in the 2020 baseline where the source is grounded for all years, and let 2021 to 2025 inherit it. Remove the payer-side bindings and their `dependency_classifications` at the baseline, and remove the 2024 (193) and 2025 (190) alternates in their own revisions. Introduce a ledger 0599 binding in the first revision whose ledger income binding exists (2024, `.../2024/bindings/0001-declarations.toml:170`), with 2025 inheriting it. Earlier years stay manual until the ledger income family is grounded there. How disagreement is handled must be chosen: alternate bindings refuse on any difference, while a cross-check needs a typed advisory or blocking predicate.

Not investigated here:

- DGT criteria on which year a withholding belongs to when payment and accrual straddle years.
- The datos fiscales file format.
- Negative and complementaria Modelo 130 results for 0604.
- 0598 withholding on urban rentals run as an activity.
- Per-member 184 attribution.
- How casillas 0600 to 0606 are sourced beyond "manual".

## Sources

- https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764 (LIRPF consolidated text, arts. 79, 98, 99, 101, 105; retrieved 2026-09-27)
- https://www.boe.es/buscar/act.php?id=BOE-A-2007-6820 (RIRPF consolidated text, arts. 74, 75, 76, 95, 108, 109, 110; retrieved 2026-09-27)
- https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/irpf-2025/c01-campana-declaracion-renta/borrador-declaracion-irpf/obtencion-borrador-declaracion-irpf-datos-fiscales.html (retrieved 2026-09-27)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2022/ManualRenta2022_es_es.pdf (in-repo copy `src/cadrumo/_data/corpus/manuals/renta/2022/part1/source.pdf.extracted.md:62321-62343`)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2023/ManualRenta2023_es_es.pdf (in-repo copy `src/cadrumo/_data/corpus/manuals/renta/2023/part1/source.pdf.extracted.md:71507-71536`)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2024/ManualRenta2024Tomo1_es_es.pdf (in-repo copy `src/cadrumo/_data/corpus/manuals/renta/2024/part1/source.pdf.extracted.md:58475-58504`)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf (in-repo copy `src/cadrumo/_data/corpus/manuals/renta/2025/part1/source.pdf.extracted.md:1272-1445`, `:54444-54468`)
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/06-100-diccionario-declaracion-individual-ejercicio-2022-actualizado-17-05-2023-365-kb-otros-fi.properties:893-907`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/07-100-diccionario-declaracion-individual-ejercicio-2023-actualizado-29-01-2026-382-kb-otros-fi.properties:912-926`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/08-100-diccionario-declaracion-individual-ejercicio-2024-actualizado-29-01-2026-393-kb-otros-fi.properties:932-946`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_100/files/01-100-diccionario-declaracion-individual-ejercicio-2025-actualizado-14-04-2026-416-kb-otros-fi.properties:261-265`, `:959-973`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_190/files/01-190-orden-eha-3127-2009-de-10-de-noviembre-actualizada-por-orden-hac-1431-2025-de-3-de-dicie.pdf.extracted.md:592`
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_111/files/modelo-111-instrucciones.html` (casilla 28)
- `src/cadrumo/_data/corpus/aeat_official/instructions/modelo_130/files/modelo-130-instrucciones.html` (casillas 06 and 19)
- `src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-79.html.extracted.md`, `ley-35-2006-art-98.html.extracted.md`, `ley-35-2006-art-101.html.extracted.md`, `rd-439-2007-art-75.html.extracted.md`, `rd-439-2007-art-95.html.extracted.md`, `rd-439-2007-art-108.html.extracted.md` (the in-repo art. 108 excerpt stops at apartado 2; apartado 3 was read from the BOE consolidated text), `rd-439-2007-art-109.html.extracted.md`, `rd-439-2007-art-110.html.extracted.md`
- Registry and code locators as cited inline in the findings above.
