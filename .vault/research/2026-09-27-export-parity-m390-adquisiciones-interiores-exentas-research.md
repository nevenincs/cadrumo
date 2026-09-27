---
tags:
  - '#research'
  - '#export-parity'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:ce65968e976b0f829203ec7d3064fe62bac74bd7b6d81a5512b639049a5c5e00'
related: []
---
# `export-parity` research: `m390 adquisiciones interiores exentas`

Question: what must Modelo 390 apartado 11 box [230] "Adquisiciones interiores exentas" contain for ejercicios 2022 to 2025, where does that data live in Cadrumo's ledger and IVA model, and how can the box be bound under the delta-keyed registry. It matters because the box is unbound on every revision, so the annual return of an autonomo who pays an exempt insurance premium or bank interest carries zeros in [230] on the wire, and only a non-blocking advisory says otherwise.

Evidence picture: the box is ledger-derived from received business rows. The official AEAT instructions for 2024 and 2025 define it as domestic acquisitions of goods and services exempt under LIVA art. 20 or taxed at 0 %. A DGT binding consulta confirms that exempt acquisitions go to [230] and never to Modelo 303. The ledger already produces a typed observation for an exempt purchase. What is missing is the binding, a trustworthy classification of which expense rows are exempt, and evidence for the 2022 and 2023 instruction wording. A second pass on the same day examined the insurance premium tax and a dwelling let partly used as an office. No official source settles the tax. AEAT and DGT settle the dwelling: such a let is not exempt. The options are framed at the end. The choice belongs to the ADR.

## Findings

### The official definition: art. 20 exempt acquisitions of goods and services, and 0 % acquisitions in 2024 and 2025

- The AEAT instructions for ejercicio 2025 (page 24) and ejercicio 2024 (page 27) read identically. Box [230] takes the amount ("importe") of domestic acquisitions of goods and services that are exempt, or taxed at the zero rate, "según lo dispuesto en el artículo 20" of the LIVA. Both editions preface apartado 11 with the rule that its amounts are entered whether or not they were already included in earlier apartados. Sources: https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/Instrucciones_modelo_390-2025.pdf (retrieved 2026-09-27, sha256 `26028dcb9936...d3301d`, 355,432 bytes, PDF created 2026-02-24) and https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/instr390.pdf (retrieved 2026-09-27, sha256 `2af493936c21...16a0f3`, 760,685 bytes, PDF created 2024-12-16, internally dated to ejercicio 2024).
- Goods and services are both named. No supply-nature filter applies.
- Only art. 20 is named. The siblings name their own articles: [109] arts. 26 and 140 bis plus 0 % intra-Community acquisitions, [231] arts. 27 to 67 plus 0 % imports (same pages). Exemptions under arts. 21 to 25 (exports, assimilated operations, free zones and warehouses, intra-Community supplies) are not in [230]'s wording.
- The amount is "importe". [230]'s text carries no "excluido el IVA" or "base imponible" qualifier, while [232] says "importe total, excluido el Impuesto sobre el Valor Añadido" (same pages). For exempt and 0 % operations no IVA is charged, so the invoice amount and the taxable base coincide except where another tax is embedded in the price (see "Open points").
- The 0 % half has no other annual home. The 2025 instructions list the deducible interior base boxes only at 2, 4, 5, 7.5, 10 and 21 % (page 8 to 9). The designs agree: interior current-goods deducible bases exist at 4, 5, 10 and 21 % in 2022 (`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/14-390-ejercicio-2022-actualizado-04-01-23-491-kb-xlsx.xlsx.extracted.md:241-247`) and at 2, 4, 5, 7.5, 10 and 21 % in 2025 (`01-390-ejercicio-2025-actualizado-05-12-2025-544-kb-xlsx.xlsx.extracted.md:296-306`). No design from 2022 to 2025 has a 0 % deducible interior box.
- The wording changed over time, and the exact year is unproven. An AEAT instruction edition for ejercicio 2017 (PDF created 2018-01-02), hosted by a third party at https://www.aece.es/descargararchivo_docnoticias_1744, reads "exentas del Impuesto sobre el Valor Añadido según lo dispuesto en el artículo 20", without "o a tipo cero". That copy is orientation only. The AEAT Sede publishes only the current and previous editions: the procedure page links "Instrucciones 2025" and "Instrucciones 2024", and the ejercicio-2022 and ejercicio-2023 pages carry no instruction document (https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-390-iva-declaracion-resumen-anual_/ejercicio-2022.html, `.../ejercicio-2023.html`). web.archive.org was unreachable from this host. Whether the 2022 and 2023 editions include "o a tipo cero" is therefore not established. Orden HFP/1124/2022 first added 0 % boxes to the 390. Its preamble says the forms could not declare the new 5 % and 0 % rates, and its entry-into-force clause applies it first to the 390 for ejercicio 2022 (BOE-A-2022-19290). That makes 2022 a plausible first year for the wording, but it is inference.
- The box is one per declaration, not per activity. The BOE form prints apartado 11 once on page 7, above the five per-activity prorrata rows of apartado 12 (Orden HFP/1124/2022, anexo III, page 7). In the design's page 7, the "Com" column marks the record identifiers and the prorrata rows "C" and leaves the apartado 11 fields blank (`01-390-...extracted.md:657-706`). The design prints no legend for that column, so it only corroborates.
- Box number, page and position are stable: page 7, offset 13, length 17, signed type N, from the 2015 design to 2025 (`08-390-ejercicio-2015-103-kb-pdf.pdf.extracted.md:611`, `14-390-...2022...extracted.md:570`, `15-390-ejercicio-2023-y-siguientes-489-kb-xlsx.xlsx.extracted.md:574`, `16-390-ejercicio-2024-actualizado-18-12-24-544-kb-xlsx.xlsx.extracted.md:668`, `01-390-...2025...extracted.md:663`).
- The BOE anexo prints the form label only. Orden HFP/1124/2022, anexo III, page 7, lists "Adquisiciones interiores exentas ... 230" with no per-box instructions (https://www.boe.es/boe/dias/2022/11/22/pdfs/BOE-A-2022-19290.pdf). The per-box instructions exist only as AEAT Sede documents. The Orden EHA/3111/2009 consolidated text in the corpus lists the orders that replaced anexo I: HAC/646/2021 for 2021, HFP/1124/2022 for 2022, HFP/1397/2023 for page 2 in 2023, HAC/1167/2024 for 2024, and HAC/27/2026 for 2026 (`src/cadrumo/_data/corpus/normatives/html/orden-eha-3111-2009.html.extracted.md:94-113`). None of them touches apartado 11's wording.
- The Manual práctico IVA lists "Adquisiciones interiores exentas" among the operaciones específicas in every edition from 2020 to 2025 without defining it (`src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md:10939-10942`; 2024 `:11129`, 2023 `:9791`, 2022 `:9288`).

### DGT V2503-16: exempt acquisitions belong in [230] and never in Modelo 303

- Consulta vinculante V2503-16, SG de Impuestos sobre el Consumo, dated 08/06/2016, concerns received invoices for civil-liability insurance and employee language courses, both exempt under art. 20. It answers that Modelo 303 must not include these operations and that Modelo 390 must include them in casilla 230. It also answers that the libro registro de facturas recibidas must record invoices for exempt and not-subject operations, and that Modelo 347 includes them above its threshold. It notes that RD 1619/2012 does not oblige an invoice for many art. 20 operations. Text read through the DGT's own search service at https://petete.tributos.hacienda.gob.es/consultas/?num_consulta=V2503-16 on 2026-09-27; that page is script-driven.
- Consequence: the quarterly 303 correctly declares nothing for these rows. The annual [230] total must come from the same ledger rows, because no 303 box exists to fold forward.

### Not subject is not exempt

- LIVA art. 20 exempts operations that are subject. Operations outside the taxable event (LIVA art. 7, or no operation at all, such as a Social Security quota or a tax) are neither exempt nor 0 %. [230]'s wording admits only "exentas o a tipo cero".
- The registry already keeps these apart. The 303 casilla-120 commentary separates `operacion_no_sujeta` (art. 7) and `domestic_not_subject` from exempt and localisation cases (`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023/bindings/0001-declarations.toml:122-149`). The export-parity seed records RETA quotas as `operacion_no_sujeta` (`dev/acceptance/export_parity/seed.py:255-266`).

### LIVA art. 20 applied to an autonomo's expenses

From the bundled consolidated text (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-20.html.extracted.md`):

- 1º universal postal service (`:4`). 3º care by medical or health professionals (`:13`). 9º education by qualifying entities (`:41`). 10º private lessons by natural persons (`:49`).
- 12º member services of non-profit bodies for statutory dues, expressly including Colegios profesionales, subject to no distortion of competition (`:55-57`).
- 16º insurance, reinsurance and capitalisation, including their mediation and the "modalidades de previsión" (`:71-73`).
- 18º financial operations: deposits and the payment services tied to them, credit and loans, guarantees, transfers and payment cards (`:76-94`). It excludes collection management (gestión de cobro), services to the assignor under factoring, and custody or management of securities (`:78`, `:98`).
- 22º second and later deliveries of buildings (`:117`), which art. 20.Dos lets the transferor waive, together with 20º, for a deducting acquirer (`:163`).
- 23º lettings of buildings used exclusively as dwellings (`:140-144`). The exemption excludes furnished lets with hotel services and lettings "asimilados a viviendas" under the LAU (`:145-152`).

### An AEAT worked example declares an exempt insurance invoice in [230] at the amount billed

- The Manual práctico IVA's Modelo 390 worked example includes item (40): the insurer that covered a sale "le factura 500 euros", and the manual classifies the operation as exempt. The item is identical in every bundled edition (`src/cadrumo/_data/corpus/manuals/iva/2022/source.pdf.extracted.md:9682`, 2023 `:10182`, 2024 `:11530`, 2025 `:11356`).
- AEAT's filled Modelo 390 for that example prints 500,00 on the [230] row of page 7. Checked in the 2023 and 2024 editions: https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/IVA_2023/Imagenes/C9-mod390_es_es.pdf (sha256 `92fb74ac7741...`, PDF created 2023-07-18) and `.../IVA_2024/Imagenes/Cap_9_390_es_es.pdf` (sha256 `5deea54097e0...`, PDF created 2024-09-17), both retrieved 2026-09-27. The value and the label share one text row by character position. The same form prints 1.200,00 on the [232] row, the example's gifts to customers. The analogous 2025 path returns HTTP 404.
- This is an independent official oracle for the exempt half. The corpus already grounds the same example's annual cuota totals, but not [230] (`src/cadrumo/_data/corpus/manual_oracles/modelo-390-2024-resumen-anual-cuatro-trimestres.json`). The filled form itself is not in the corpus.
- It does not settle the insurance premium tax. The example states one billed amount and mentions no tax.

### No official source settles whether the insurance premium tax belongs in [230]

- The [230] instruction names no tax to add or to remove. Both editions ask for "el importe de las adquisiciones interiores de bienes y servicios exentas o a tipo cero" (2025 page 24, 2024 page 27, re-read 2026-09-27 with the hashes above). A full-text search of both editions finds no mention of the insurance premium tax (IPS), of insurance premiums, or of the Consorcio surcharges.
- The LIVA's own "importe" concepts exclude only IVA:
  - Art. 78.Dos.4º brings into the taxable base "los tributos y gravámenes de cualquier clase que recaigan sobre las mismas operaciones gravadas, excepto el propio Impuesto sobre el Valor Añadido" (`src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:1739-1740`).
  - Art. 121.Uno defines the volumen de operaciones as the "importe total", excluding only IVA, the recargo de equivalencia and the compensación a tanto alzado, exempt operations included (`:2690`). Art. 104.Dos takes the "importe total" for the prorrata (`:2411-2413`).
  - The 390 instructions exclude IVA explicitly where they mean it: [232] is the "importe total, excluido el Impuesto sobre el Valor Añadido".
  - Art. 78.Dos.4º speaks of "operaciones gravadas". No source found says whether it reaches an exempt operation.
- The IPS law separates the premium from the tax. Ley 13/1996 art. 12, from the BOE consolidated text (https://www.boe.es/buscar/act.php?id=BOE-A-1996-29117, retrieved 2026-09-27; not in the corpus):
  - Uno: the IPS is an indirect tax on insurance and capitalisation operations.
  - Ocho: its base is the premium, the consideration for the insured operation, excluding the Consorcio de Compensación de Seguros and CLEA surcharges and "los demás tributos que recaigan directamente sobre la prima".
  - Nueve and Diez: the insurer is the sujeto pasivo and must pass the tax on in full to the policyholder, following the IVA's repercusión rules.
  - Once: the rate is 8 %.
  - Cinco.1 b) and i): life insurance and health insurance are exempt from the IPS, so their receipts carry none.
- No DGT consulta that answers the question was found:
  - Web searches found consultas on recharged collective premiums (V0482-24, read in a third-party copy), the insurer's invoicing duty for exempt insurance (V1508-17, title only) and premiums paid as suplidos (V2656-20, title only). None addresses the IPS in the amount of an exempt acquisition or in [230].
  - The DGT's own search service was unusable on 2026-09-27. Number lookups returned HTTP 500. Free-text queries returned 502, 504, timeouts, or no results for "casilla 230" and "adquisiciones interiores exentas".
  - The absence is a search result, not proof that no consulta exists.
- Two readings remain, and no official source adopts either for [230]:
  - Inclusion follows the LIVA's pattern of excluding only IVA from an "importe". It cannot understate the box.
  - Exclusion follows the IPS law, which keeps the tax and the surcharges out of the premium and passes the tax on as the IVA is passed on.
- The Consorcio and CLEA surcharges raise the same question. Their own IVA character was not established here.

### Exempt insurance and bank receipts are outside the SII register

- AEAT SII FAQ 4.14 and 4.15 (page 60): a receipt from a credit entity for an exempt financial service, or from an insurer for an exempt insurance operation, is not recorded in the SII libro registro de facturas recibidas when RD 1619/2012 art. 3.2 imposes no invoice, because it is not an invoice. FAQ 2.24 (page 32): insurers report their premiums per customer once a year under RD 1065/2007 art. 33.1. Source: https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G417/FicherosSuministros/V_1_1/FaqGral/FAQs_10_02_2025.pdf (sha256 `12aafe906015...`, PDF created 2025-04-10, retrieved 2026-09-27).
- Consequence: [230] cannot be reconciled against an SII record for these rows. V2503-16 still requires them in [230], so the ledger row is the only source.

### A dwelling let used partly as an office is not exempt, so it contributes nothing to [230]

- 23º.b exempts buildings or parts of them "destinados exclusivamente a viviendas" (`ley-37-1992-art-20.html.extracted.md:143`).
- AEAT's IVA information page says the exemption does not apply, and the lessor charges IVA at 21 %, when the dwelling has a mixed use as a home and a professional office (https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-inmobiliarias/alquilo-vivienda-tengo-que-ingresar-iva.html, updated 2026-03-26, retrieved 2026-09-27).
- DGT V0291-20 (07/02/2020, SG de Impuestos sobre el Consumo) reaches the same result for a tenant who leased a home exclusively as a dwelling and then used part of it as a professional office:
  - The let becomes subject and not exempt, even if two contracts are signed, one for the dwelling and one for the office.
  - The tenant may deduct the IVA in proportion to the business use under art. 95.Tres, subject to the general deduction requirements.
  - Read in a third-party reproduction (https://www.iberley.es/resoluciones/resolucion-vinculante-dgt-v0291-20-07-02-2020-1528040) because the DGT service was unusable that day. It must be re-read from the DGT before the registry cites it.
- Art. 95.Tres admits a partial deduction of IVA on the "arrendamiento o cesión de uso" of an investment good used partly in the activity (`ley-37-1992.html.extracted.md:2271`). The Manual práctico IVA 2025 treats a property used as home and office the same way: deductible in the business part, with the floor-area proportion as a reasonable criterion (`manuals/iva/2025/source.pdf.extracted.md:5039-5043`).
- Consequence: [230] takes no amount from such a let. The whole rent is a taxed acquisition on the ordinary soportado route. A dwelling let exclusively as a home is a private acquisition and reaches [230] neither.
- The expense category that records the case has the wrong hint. `arrendamiento_vivienda_afecto` is, by construction, a rented dwelling used partly in the activity (`proportionality_kind = "usage_ratio_home_area"`), yet it carries `iva_hint = "exempt_or_non_subject"` (`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:715-745`).

### Cadrumo records an exempt purchase today, but with the wrong rate tier and without trustworthy classification

- The operator records an exempt purchase as a received BUSINESS row with `--iva-category domestic_exempt --taxable-base X --iva-rate 0 --iva-amount 0` (`src/cadrumo/entrypoints/cli/tests/test_m303_zero_cuota_and_investment_inputs_cli.py:350-372`; seed `dev/acceptance/export_parity/seed.py:369-407`, `:486` and scenario `dev/acceptance/export_parity/scenario.py:276-284` for a synthetic 480.00 insurance premium per year).
- The row settles as `soportado` with the base unreduced. Only the cuota and recargo follow the business share (`src/cadrumo/application/aggregation/_iva_transaction.py:312-321`). Fact 0084 declares `domestic_exempt|received` with base required and cuota zero by law (`src/cadrumo/_data/registry/aeat/facts/0084-iva-category-component-catalogue.toml:163`). Fact 0085 admits no deduction kind for it (`0085-iva-deduction-applicability-catalogue.toml:26-30`), so the row needs none (`_iva_transaction.py:497-526`).
- The rate tier is `zero`, not `exempt`. The declared numeric rate 0 resolves through `iva_rate_kind_for` (`_iva_transaction.py:324-357`), although the registry projects the `exempt` tier to `domestic_exempt` and `zero` to `domestic_zero` (`src/cadrumo/_data/registry/aeat/facts/0094-iva-rate-slot-catalogue.toml:49-54`). The Modelo 303 casilla 59 and 60 selectors already admit both tiers for cuota-less categories (`src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/bindings/0001-declarations.toml:174-188`).
- Without an explicit category, a 0 rate reads as a taxable 0 % purchase. The effective category comes from the rate tier (`_iva_transaction.py:426-450`), so an exempt premium entered without `--iva-category` becomes `domestic_zero`, which then demands a deduction classification (`src/cadrumo/application/aggregation/tests/test_zero_cuota_purchases_need_no_deduction_classification.py:266-296`).
- The expense catalogue carries an IVA hint, but it cannot discriminate. The `--category-id` catalogue is fact 0064 (`src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:760-773`), and each category carries `iva_hint` from the vocabulary `general, exempt_or_non_subject, non_deductible_input` (`:824`), stable from 2022 to 2026. The hint merges exempt with not subject. Production code only loads it (`src/cadrumo/domain/categories/registry.py:194-200`, `src/cadrumo/domain/categories/profile.py:49`). No default, suggestion or refusal reads it.
- Categories hinted `exempt_or_non_subject`, read against art. 20:
  - Exempt with a fixed article: `seguros_responsabilidad_civil`, `seguros_salud_autonomo`, `vehiculo_seguro` and `mutualidad_alternativa` (16º, previsión included); `gastos_financieros` (18º, interest and loans).
  - Exempt only on conditions the row does not carry: `cuotas_colegiales` (12º, statutory dues, no distortion); `gastos_bancarios` (18º, but collection management, factoring, custody and POS rental are taxed).
  - Not exempt: `arrendamiento_vivienda_afecto`. A dwelling let used partly in the activity loses 23º.b (see "A dwelling let used partly as an office").
  - Not subject, or not an operation: `cuotas_autonomos_ss`, `ibi_local_afecto`, `ibi_vivienda_afecto`, `tributos_fiscalmente_deducibles`, `comunidad_vivienda_afecto` and `amortizacion_vivienda_afecto`.
  - Mis-hinted: `manutencion_dietas_nacional` (restaurant services are taxed) and `manutencion_dietas_extranjero` (foreign VAT, outside Spanish IVA).
  - Hinted `general` although sometimes exempt: `formacion_profesional` (9º and 10º, depending on the provider). No category covers postal or medical services.
- The exemption-article discriminator is mislabelled and unreachable. The observation carries an optional `exemption_article`, and the selector can filter on `exemption_articles` (`src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py:124`, `:288-290`, `:396-407`). Its vocabulary has three members (`src/cadrumo/_data/registry/aeat/facts/0098-iva-statutory-schema-vocabulary.toml:79-88`). It labels `art_20_uno_8` as education, but 8º is social assistance and education is 9º (corpus `:27`, `:41`). It labels `art_20_uno_14` as health, but 14º is cultural services and health professionals are 3º (`:65`, `:13`). No CLI option sets the field. A grep of `src/cadrumo/entrypoints` finds none, and only tests construct it.
- The ledger cannot represent a credit note on an exempt purchase. `taxable_base` is non-negative (`src/cadrumo/domain/transactions/models.py:736-741`), and signed amounts exist only through the `rectification` deduction kind. Fact 0085 pairs that kind with deducible categories only (`0085-...toml:34`, `:51-58`; `src/cadrumo/domain/iva/deduction_facts.py:130-163`). A refund of an exempt premium or bank fee therefore has no supported path. Recorded as INCOMING, it would become an issued exempt supply.
- Bank fees without an invoice pass the evidence gate. `domestic_exempt` is in the `evidence_exempt` projection (`0084-...toml:107`), so the deductible-evidence gate ignores the row (`src/cadrumo/application/modelo/_ledger_evidence_gate.py:141`). A row imported from a statement without IVA facts is refused with a missing-fact reason before it becomes an observation (`src/cadrumo/application/aggregation/_iva_transaction.py:266-289`).

### No binding draws the base today, and the gap surfaces only as advisories

- The `ledger_iva_aggregation` selector axes are categories, rate kinds, flow, fact, observation roles, cash-accounting treatments, and optionally applied rates and exemption articles (`ledger_iva_bindings.py:278-407`). An empty match resolves to 0 (`:893`), so the value alone cannot tell "no exempt purchases" from "exempt purchases never classified".
- Across 303 and 390, no binding selects `domestic_exempt`, `domestic_not_subject`, `operacion_no_sujeta`, or `domestic_zero` on the received side. A grep of every `modelos/{303,390}/revisions/*/bindings` fragment finds only `domestic_zero` on the repercutido side (`390/revisions/2022/bindings/0001-declarations.toml:312`, `:497`, `:509`). The test `test_neither_row_reaches_a_declared_box_on_either_form` asserts this for 303 1T and 390 0A in 2025 and names [230] as the open gap (`test_zero_cuota_purchases_need_no_deduction_classification.py:338-377`).
- The base surfaces as `unrouted_declarable_quantity` (`src/cadrumo/application/aggregation/modelo_bindings.py:396`, `:475-487`). The issue is persisted on the calculation revision (`src/cadrumo/domain/modelos/calculation_revision.py:414-446`), but it blocks neither verification nor export for IVA. Only OSS `unrouted_observation` and the IVA evidence reasons block (`src/cadrumo/application/modelo/verification_actions.py:1402-1470`, `:1506-1516`; `src/cadrumo/application/modelo/export.py:490-503`). The CLI test shows the advisory naming `domestic_exempt` on a 303 quarter (`test_m303_zero_cuota_and_investment_inputs_cli.py:430-435`).
- The structural "unroutable base category" screen runs for Modelo 303 only, "pending Modelo 390 coordination" (`modelo_bindings.py:397-411`).
- [230] is a manual casilla today. The declaration has no `binding` and no `input_kind` (`src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/casillas/0001-declarations.toml:1820-1831`), and the default input kind is `manual` (`src/cadrumo/domain/calculations/registry/schema_surfaces.py:345`).
- The export field exists on every revision's page 7, keyed by casilla id, signed, optional and zero-padded (for 2025, `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/export/0011-record-modelo-390-page-07.toml:97-114`). An absent optional slot renders as its zero fill (`src/cadrumo/domain/calculations/registry/fixed_width_codec.py:243-259`, `:386-402`). On the fichero, an unclassified 480.00 premium and a genuine zero look identical.

### Precedents for the binding and its placement

- 390 base boxes already bind this family. The domestic soportado base selects the three positive tiers (`390/revisions/2022/bindings/0001-declarations.toml:323-328`), and volumen exportaciones selects the export categories (`:671-682`). Bound casillas carry `input_kind = "bound"` and `binding = ...` (`390/revisions/2022/casillas/0001-declarations.toml:87-88`).
- Filing years: floor 2022, horizon 2026 (`src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml:18-20`). Revision 2021 is applicability-grade below the floor (`390/revisions/2021/revision.toml`). 2022 authors [230] natively. 2023, 2024 and 2025 inherit through `family_storage_baseline` 2022, 2023 and 2024.
- Later editions patch inherited bindings through `family_overrides` with `family = "bindings"` (`390/revisions/2024/revision.toml:374-413`). Inherited casillas are patched through `casilla_overrides` (`390/revisions/2022/revision.toml:108-146`).
- The construct `modelo-390-iva-resumen-anual` enumerates `casilla_ids` and `bindings` (`390/revisions/2022/constructs/0001-declarations.toml:72`, `:160`). Editions 2023, 2024 and 2025 patch it with positional `sequence_order` vectors (`390/revisions/2023/revision.toml:817-821`, `2024/revision.toml:361-365`, `2025/revision.toml:450-454`), so a new baseline member shifts every later position. The derived completeness manifest lives in 2022 and is scoped in later editions.
- Authoring goes through `dev/registry` (`dev/registry/README.md`; `.claude/skills/aeat-authority-registry-authoring/references/authoring-commands.md`): author the delta, inspect with `inspect_authoring_candidate`, normalise and apply with `dev.registry.edition_delta_migration`, verify with `dev.registry.registry_collapse_verification`, and publish with `dev.registry.pipeline publish-authority`. The page-7 export fields are generated targets.

### Sources the corpus lacks, and the capture route

- `aeat-modelo-390-procedure` is only the Sede landing page (`src/cadrumo/_data/registry/aeat/legal/iva.toml:873-883`). That page links both instruction PDFs, but neither is bundled.
- Precedent for an instructions PDF: `aeat-modelo-190-instructions-2025`, kind `manual_pdf`, tier `official_source_guidance`, under `corpus/aeat_official/instructions/modelo_190/files/` (`src/cadrumo/_data/registry/aeat/legal/irpf.toml:2813-2823`).
- Tooling: `dev/corpus/sync_aeat_record_design_corpus.py` handles record designs only, and `dev/corpus/fetch_boe_normative.py` handles BOE normatives. PDF text sidecars come from `just generate-corpus-text` (`dev/corpus/extract_manual_corpus_text.py`). Identity fields are in `dev/registry/compiler/corpus_catalogue.py`. No DGT-consulta source kind exists in the legal catalogues; the kinds are `ley`, `orden`, `record_design`, `instructions`, `manual_pdf`, `form_spec`, `real_decreto` and others.

### Sibling boxes in apartado 11

All eleven apartado 11 casillas on 390/2022 are unbound (`390/revisions/2022/casillas/0001-declarations.toml:1820-1964`). Mechanisms differ:

- [109], exempt and 0 % intra-Community acquisitions: same family. The candidates are `intra_community_triangulation` received, whose cuota is zero by law (`0084-...toml` received rows), and `intra_community_acquisition_reverse_charge` at an applied rate of 0.00. This is a follow-on with the same mechanism.
- [231], exempt and 0 % imports: the ledger has no discriminator for an art. 27 to 67 exemption on `import_third_country`. That is a modelling gap, not just a binding.
- [232], bases with non-deductible soportado (arts. 95, 96): needs a non-deductible base quantity the observation does not carry. The base is unreduced, and only the cuota is scaled.
- [113] and [523], reverse-charge informative boxes, and [654] to [657], criterio de caja: same family. [654] to [657] would use the `operation_informational` role, as Modelo 303 does (`303/revisions/2022/bindings/0001-declarations.toml:285-335`). [111] (REDEME) rarely applies to an autonomo.
- Outside apartado 11, [105] "operaciones exentas sin derecho a deducción" is also unbound (`390/revisions/2022/casillas/0001-declarations.toml:2426-2435`). It is the supply-side twin (`domestic_exempt`, repercutido).

### Coordination

- Plan step `S13` of `2026-09-26-export-parity-plan` (registry conformance rectification) lists Modelo 390. A sibling effort binds 303 and 390 investment-goods boxes in the same 390 bindings, casillas, constructs and revision files. The construct's positional `sequence_order` makes these edits collide unless one writer applies them in sequence through the converter.
- An exempt second delivery of a building (20.Uno.22º without waiver) is an investment-asset acquisition that also belongs in [230]. It touches the investment-goods work.
- The 390 [84]/[86] silent zeros are a separate finding.

### Options the ADR must settle

- Population years:
  - A: exempt only, every year.
  - B: exempt in every supported year, plus 0 % where the captured instructions say so (2024 and 2025 today), with 0 % purchases in 2022 and 2023 kept as an explicit advisory until those editions are captured.
  - C: exempt plus 0 % in every year on the assumption that the wording is constant.
  - The evidence favours B. C asserts an unverified edition, and A omits the 0 % purchases that have no other box in 2024 and 2025.
- Rate tier:
  - Admit both `zero` and `exempt` in the selector, following the casilla 59 and 60 precedent.
  - Or change the ledger to resolve `domestic_exempt` to the `exempt` tier.
  - The first is sufficient for [230]. The second is a separate correctness fix.
- Classification:
  - Operator-declared only, plus a candidate advisory.
  - Or split `exempt_or_non_subject` into typed exempt and not-subject hints with default exemption articles, refusing a 0-rate row in an exempt-hinted category that has no explicit IVA category.
  - Or LLM inference.
  - The evidence favours the split with refusal: the hint exists, is unused and is wrong for several categories, and an inferred default would be filing-bound.
- Amount under partial business use: full base, matching the ledger's unreduced-base convention and the libro registro, or the business share. No official text addresses exempt acquisitions directly.
- 303 residual advisory: keep it as is, or reclassify it as "declared on the annual return [230]".

### Open points not resolved by this research

- The 2022 and 2023 instruction wording ("o a tipo cero").
- Whether the insurance premium tax and the Consorcio and CLEA surcharges belong in the amount. The second pass narrowed this to two readings but found no official source that settles it (see "No official source settles whether the insurance premium tax belongs in [230]").
- How a refund of an exempt purchase should reduce [230].
- The text of V0291-20 from the DGT's own service, which was unusable on 2026-09-27.

The second pass settled one earlier open point: a dwelling let used partly as an office does not keep the 23º.b exemption.

## Sources

- https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/Instrucciones_modelo_390-2025.pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G412/instr390.pdf
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G412.shtml
- https://sede.agenciatributaria.gob.es/Sede/todas-gestiones/impuestos-tasas/iva/modelo-390-iva-declaracion-resumen-anual_/ejercicios-anteriores.html
- https://petete.tributos.hacienda.gob.es/consultas/?num_consulta=V2503-16
- https://www.boe.es/boe/dias/2022/11/22/pdfs/BOE-A-2022-19290.pdf
- https://www.boe.es/diario_boe/xml.php?id=BOE-A-2024-21961
- https://www.boe.es/diario_boe/xml.php?id=BOE-A-2026-1761
- https://www.aece.es/descargararchivo_docnoticias_1744 (third-party copy of the ejercicio-2017 AEAT instructions; orientation only)
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/IVA_2023/Imagenes/C9-mod390_es_es.pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/IVA_2024/Imagenes/Cap_9_390_es_es.pdf
- https://sede.agenciatributaria.gob.es/static_files/Sede/Procedimiento_ayuda/G417/FicherosSuministros/V_1_1/FaqGral/FAQs_10_02_2025.pdf
- https://sede.agenciatributaria.gob.es/Sede/iva/iva-operaciones-inmobiliarias/alquilo-vivienda-tengo-que-ingresar-iva.html
- https://www.boe.es/buscar/act.php?id=BOE-A-1996-29117 (Ley 13/1996, art. 12)
- https://www.iberley.es/resoluciones/resolucion-vinculante-dgt-v0291-20-07-02-2020-1528040 (third-party reproduction of DGT V0291-20; to be re-read from the DGT)
- https://www.iberley.es/resoluciones/resolucion-vinculante-direccion-general-tributos-v0482-24-02-04-2024-11658240 (third-party reproduction of DGT V0482-24; orientation only)
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:1739`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2271`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992.html.extracted.md:2690`
- `src/cadrumo/_data/corpus/manuals/iva/2024/source.pdf.extracted.md:11530`
- `src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md:5039`
- `src/cadrumo/_data/corpus/manual_oracles/modelo-390-2024-resumen-anual-cuatro-trimestres.json`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/01-390-ejercicio-2025-actualizado-05-12-2025-544-kb-xlsx.xlsx.extracted.md:663`
- `src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_390/files/14-390-ejercicio-2022-actualizado-04-01-23-491-kb-xlsx.xlsx.extracted.md:570`
- `src/cadrumo/_data/corpus/manuals/iva/2025/source.pdf.extracted.md:10939`
- `src/cadrumo/_data/corpus/normatives/html/ley-37-1992-art-20.html.extracted.md:1`
- `src/cadrumo/_data/corpus/normatives/html/orden-eha-3111-2009.html.extracted.md:94`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/casillas/0001-declarations.toml:1820`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/bindings/0001-declarations.toml:323`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2022/constructs/0001-declarations.toml:72`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2024/revision.toml:374`
- `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2025/export/0011-record-modelo-390-page-07.toml:97`
- `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2022/bindings/0001-declarations.toml:174`
- `src/cadrumo/_data/registry/aeat/facts/0064-categories-profile.toml:760`
- `src/cadrumo/_data/registry/aeat/facts/0084-iva-category-component-catalogue.toml:163`
- `src/cadrumo/_data/registry/aeat/facts/0085-iva-deduction-applicability-catalogue.toml:26`
- `src/cadrumo/_data/registry/aeat/facts/0094-iva-rate-slot-catalogue.toml:49`
- `src/cadrumo/_data/registry/aeat/facts/0098-iva-statutory-schema-vocabulary.toml:79`
- `src/cadrumo/_data/registry/aeat/legal/iva.toml:873`
- `src/cadrumo/_data/registry/aeat/legal/irpf.toml:2813`
- `src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml:18`
- `src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py:98`
- `src/cadrumo/domain/calculations/registry/fixed_width_codec.py:243`
- `src/cadrumo/domain/calculations/registry/schema_surfaces.py:345`
- `src/cadrumo/application/aggregation/_iva_transaction.py:312`
- `src/cadrumo/application/aggregation/modelo_bindings.py:396`
- `src/cadrumo/domain/modelos/calculation_revision.py:414`
- `src/cadrumo/application/modelo/verification_actions.py:1402`
- `src/cadrumo/application/aggregation/tests/test_zero_cuota_purchases_need_no_deduction_classification.py:338`
- `src/cadrumo/entrypoints/cli/tests/test_m303_zero_cuota_and_investment_inputs_cli.py:430`
- `dev/acceptance/export_parity/seed.py:255`
- `dev/registry/README.md`
- `.claude/skills/aeat-authority-registry-authoring/references/authoring-commands.md`
