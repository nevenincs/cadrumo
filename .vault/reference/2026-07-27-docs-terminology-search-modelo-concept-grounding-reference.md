---
tags:
  - '#reference'
  - '#docs-terminology-search'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# `docs-terminology-search` reference: `modelo concept grounding`

Grounding material for the 43 registry-backed modelos that remain unenrolled in
the Terminology Handbook after the enrolment source was narrowed to
registry-backed forms. It supplies, per modelo, the authoritative AEAT name held
in the registry, a candidate binding legal provision with the corpus evidence it
was verified against, existing Handbook concept ids that genuinely relate, and a
one-line English factual note as raw material.

This document deliberately contains no shipped prose. There is no
`short_description`, no `definition`, and no concept fragment here: the
taxpayer-facing wording is written by the main session, which is the sole
approval gate for that surface.

Sources consulted: the validated registry authority (`ModeloDefinition.title`,
`official_name`, `tax_domain`, `cadence`, `legal_refs`), the legal catalogue
(`LegalReference.corpus_ref`, `required_text`, `document_id`, `permalink`,
`review_status`, `reviewed_by`), the bundled normative corpus under
`src/cadrumo/_data/corpus/normatives/html/`, and the committed Handbook tree
under `src/cadrumo/_data/terminology/concepts/`. Semantic code search was not
used: its index is truncated while reporting itself healthy, so every claim here
rests on direct reads and executed measurement.

## Summary

### How the grounding was verified

The registry already declares `legal_refs` for every one of the 43 modelos, so
no provision was guessed. 175 reference citations resolve to 136 distinct legal
catalogue entries; every one of the 136 carries a `corpus_ref` and a BOE
permalink, and every `corpus_ref` resolves to a file that exists in the bundled
corpus. For each entry the `required_text` phrases were matched against the
de-tagged, accent-folded corpus text; all 175 matched.

That check was proven to bite before its result was trusted: against
`orden-hac-66-2002` the two real `required_text` phrases matched and two
fabricated control phrases did not, and the declared anchor `a1` was present
while a control anchor `a99999` was absent. A clean pass across 175 refs is only
evidence because the instrument was shown to fail on planted misses.

A provision was then classed as the modelo's *binding* one only when its
`required_text` contains both an approval phrase and the modelo's own three-digit
number. The first version of that rule required both in a single phrase and
wrongly demoted `848`, whose approval phrase and form number are separate
`required_text` entries; the rule was corrected to read the entries jointly.

Two limits are worth stating rather than leaving implied. First, 50 of the 136
entries carry `reviewed_by` recording them as agent-prepared and pending
operator re-stamp, so `review_status = reviewed` is not yet an operator
ratification. Second, 48 of the 136 sit on corpus excerpts under 1500 characters
(46 órdenes, 2 leyes). For an orden's approving article a short excerpt is
expected, because the provision itself is one sentence. For the two leyes
(`ley-35-2006:art-68.3` at 974 characters and `ley-58-2003:art-93` at 1416) the
excerpt is thin, and the `required_text` was authored alongside the excerpt, so
the check confirms internal consistency rather than BOE faithfulness. The BOE
permalink is the external anchor nobody has re-verified.

### Grounding status of the 43

34 of 43 have a binding provision verified in the bundled corpus. 9 do not, in
three distinct ways, and each is reported as a blank rather than filled with a
plausible article.

- **MIS-ATTRIBUTED (3)** — `187`, `188`, `194` each cite
  `orden-eha-3377-2011:art-1`, whose verified text reads "Se aprueba el modelo
  193". Reading the corpus file confirms it: "modelo 193" occurs 37 times and is
  the subject of the approving sentence, while `187`, `188` and `194` appear only
  as scope carve-outs, naming rentas that must be declared on those forms
  *instead of* on 193. That orden approves modelo 193 and does not approve these
  three. The evidence gate passes anyway, because the cited text genuinely exists
  in the cited file — the gate validates that a phrase is present, not that the
  provision belongs to the modelo citing it.
- **FRAMEWORK-ONLY (5)** — `117`, `126`, `128`, `220`, `296` cite only framework
  provisions (LIRPF art. 25 and art. 99, RD 439/2007 art. 108, LIS art. 124,
  TRLIRNR art. 24) or a deadline article, with no provision approving the form.
  A search of the bundled corpus finds no approving text for `117`, `126` or
  `220` at all. `296` cites `orden-hac-56-2024:art-1`, whose verified text
  concerns "El anexo II, modelo 123" — the same mis-attribution shape as the
  three above, though a candidate approving orden for 296 does exist in the
  bundle.
- **UNPINNED (1)** — `345` cites `orden-hfp-823-2022:art-1`, whose approval
  phrase is the bare "Se aprueba el modelo" with no form number in the
  `required_text`. The citation is plausibly correct; it simply is not evidenced
  by the text as recorded, so it should be re-pinned before use.

| Modelo | Status | Binding provision | Verified in bundled corpus |
|---|---|---|---|
| `038` | VERIFIED | `orden-hac-66-2002:art-1` | `corpus/normatives/html/orden-hac-66-2002.html#a1` |
| `117` | FRAMEWORK-ONLY | — none among its refs | — |
| `121` | VERIFIED | `orden-hfp-105-2017:art-1` | `corpus/normatives/html/orden-hfp-105-2017.html#a1` |
| `122` | VERIFIED | `orden-hfp-105-2017:art-5` | `corpus/normatives/html/orden-hfp-105-2017.html#a5` |
| `126` | FRAMEWORK-ONLY | — none among its refs | — |
| `128` | FRAMEWORK-ONLY | — none among its refs | — |
| `136` | VERIFIED | `orden-hap-70-2013:art-5` | `corpus/normatives/html/orden-hap-70-2013.html#a5` |
| `140` | VERIFIED | `orden-hac-177-2020:art-1` | `corpus/normatives/html/orden-hac-177-2020.html#a1` |
| `143` | VERIFIED | `orden-hap-2486-2014:art-1` | `corpus/normatives/html/orden-hap-2486-2014.html#a1` |
| `145` | VERIFIED | `resolucion-dgt-2011-01-03-modelo-145:aprobacion` | `corpus/normatives/html/boe-a-2011-208-modelo-145.html#primero` |
| `156` | VERIFIED | `orden-hac-3580-2003:art-1` | `corpus/normatives/html/orden-hac-3580-2003.html#a1` |
| `165` | VERIFIED | `orden-hap-2455-2013:art-1` | `corpus/normatives/html/orden-hap-2455-2013.html#a1` |
| `179` | VERIFIED | `orden-hac-612-2021:art-1` | `corpus/normatives/html/orden-hac-612-2021.html#a1` |
| `181` | VERIFIED | `orden-eha-3514-2009:art-1` | `corpus/normatives/html/orden-eha-3514-2009.html#a1` |
| `182` | VERIFIED | `orden-eha-3021-2007:art-1` | `corpus/normatives/html/orden-eha-3021-2007.html#a1` |
| `185` | VERIFIED | `orden-hac-1197-2025:art-1` | `corpus/normatives/html/orden-hac-1197-2025.html#a1` |
| `186` | VERIFIED | `orden-hac-539-2003:art-1` | `corpus/normatives/html/orden-hac-539-2003.html#a1` |
| `187` | MIS-ATTRIBUTED (text approves 193) | `orden-eha-3377-2011:art-1` | `corpus/normatives/html/orden-eha-3377-2011.html#articulo-1` |
| `188` | MIS-ATTRIBUTED (text approves 193) | `orden-eha-3377-2011:art-1` | `corpus/normatives/html/orden-eha-3377-2011.html#articulo-1` |
| `189` | VERIFIED | `orden-eha-3481-2008:art-1` | `corpus/normatives/html/orden-eha-3481-2008.html#a1` |
| `194` | MIS-ATTRIBUTED (text approves 193) | `orden-eha-3377-2011:art-1` | `corpus/normatives/html/orden-eha-3377-2011.html#articulo-1` |
| `216` | VERIFIED | `orden-eha-3290-2008:art-1` | `corpus/normatives/html/orden-eha-3290-2008.html#a1` |
| `220` | FRAMEWORK-ONLY | — none among its refs | — |
| `222` | VERIFIED | `orden-hfp-227-2017:art-2` | `corpus/normatives/html/orden-hfp-227-2017.html#a2` |
| `231` | VERIFIED | `orden-hfp-1978-2016:art-1` | `corpus/normatives/html/orden-hfp-1978-2016.html#a1` |
| `233` | VERIFIED | `orden-hac-1400-2018:art-1` | `corpus/normatives/html/orden-hac-1400-2018.html#a1` |
| `234` | VERIFIED | `orden-hac-342-2021:art-1` | `corpus/normatives/html/orden-hac-342-2021.html#a1` |
| `238` | VERIFIED | `orden-hac-72-2024:art-1` | `corpus/normatives/html/orden-hac-72-2024.html#a1` |
| `270` | VERIFIED | `orden-hap-2368-2013:art-1` | `corpus/normatives/html/orden-hap-2368-2013.html#a1` |
| `280` | VERIFIED | `orden-hap-2118-2015:art-1` | `corpus/normatives/html/orden-hap-2118-2015.html#a1` |
| `289` | VERIFIED | `orden-hap-1695-2016:art-1` | `corpus/normatives/html/orden-hap-1695-2016.html#a1` |
| `296` | FRAMEWORK-ONLY | — none among its refs | — |
| `341` | VERIFIED | `orden-min-2000-12-15-m341:art-1` | `corpus/normatives/html/orden-min-2000-12-15-m341.html#a1` |
| `345` | UNPINNED (no form number) | `orden-hfp-823-2022:art-1` | `corpus/normatives/html/orden-hfp-823-2022.html#a1` |
| `361` | VERIFIED | `orden-eha-789-2010:art-7` | `corpus/normatives/html/orden-eha-789-2010.html#a7` |
| `379` | VERIFIED | `orden-hfp-1415-2023:art-1` | `corpus/normatives/html/orden-hfp-1415-2023.html#a1` |
| `380` | VERIFIED | `orden-eha-1308-2005:art-1` | `corpus/normatives/html/orden-eha-1308-2005.html#a1` |
| `490` | VERIFIED | `orden-hac-590-2021:art-1` | `corpus/normatives/html/orden-hac-590-2021.html#a1` |
| `576` | VERIFIED | `orden-eha-3851-2007:art-1` | `corpus/normatives/html/orden-eha-3851-2007.html#a1` |
| `592` | VERIFIED | `orden-hfp-1314-2022:art-1` | `corpus/normatives/html/orden-hfp-1314-2022.html#a1` |
| `604` | VERIFIED | `orden-hac-510-2021:art-1` | `corpus/normatives/html/orden-hac-510-2021.html#a1` |
| `763` | VERIFIED | `orden-eha-1881-2011:art-1` | `corpus/normatives/html/orden-eha-1881-2011.html#a1` |
| `848` | VERIFIED | `orden-hac-85-2003:art-1` | `corpus/normatives/html/orden-hac-85-2003.html#a1` |

### Authoritative names, relations, and factual notes

The name column is the registry's `official_name`, trimmed of its leading
"Modelo NNN." prefix. It is authoritative data, not invention, and is the anchor
for any prose written later. Related ids were checked against the committed
Handbook tree; every id named below exists today. The note is English raw
material describing what the form is for, not shipped wording.

| Modelo | Domain / cadence | Official AEAT name | Related (existing ids) | Factual note |
|---|---|---|---|---|
| `038` | informative / monthly | Relación de operaciones realizadas por entidades inscritas en registros públicos. Declaración informativa. | `modelo`, `declaracion` | Monthly informativa filed by bodies holding public registers, listing the registered operations. |
| `117` | cross_tax / quarterly | Retenciones e ingresos a cuenta. Rentas o ganancias por transmisiones o reembolsos de acciones y participaciones de instituciones de inversión colectiva. | `irpf`, `modelo-193` | Quarterly withholding return on gains from transferring or redeeming collective-investment holdings. |
| `121` | irpf / profile_based | Deducciones por familia numerosa o por personas con discapacidad a cargo. Comunicación de la cesión del derecho a la deducción. | `irpf`, `modelo-100` | Communicates that a taxpayer not obliged to file Renta cedes the large-family or disability deduction. |
| `122` | irpf / profile_based | Deducciones por familia numerosa o por personas con discapacidad a cargo. Regularización del derecho a la deducción. | `irpf`, `modelo-100` | Regularises an over- or under-claimed family or disability deduction for a non-filer. |
| `126` | cross_tax / quarterly | Retenciones e ingresos a cuenta. Rendimientos del capital mobiliario derivados de cuentas en instituciones financieras. | `irpf`, `modelo-123`, `modelo-193` | Quarterly withholding return on interest paid on accounts at financial institutions. |
| `128` | cross_tax / quarterly | Retenciones e ingresos a cuenta. Rentas del capital mobiliario de operaciones de capitalización y contratos de seguro de vida o invalidez. | `irpf`, `modelo-123` | Quarterly withholding return on capitalisation and life or disability insurance returns. |
| `136` | cross_tax / quarterly | IRPF e IRNR. Gravamen Especial sobre los Premios de determinadas Loterías y Apuestas. Autoliquidación. | `irpf`, `autoliquidacion`, `modelo-100` | Self-assessment of the special levy on certain lottery and betting prizes. |
| `140` | irpf / profile_based | Deducción por maternidad. Solicitud de abono anticipado. | `irpf`, `modelo-100` | Applies to receive the maternity deduction monthly in advance instead of at Renta. |
| `143` | irpf / profile_based | Deducciones por familia numerosa, por ascendiente con dos hijos o por personas con discapacidad a cargo. Solicitud de abono anticipado. | `irpf`, `modelo-100` | Applies for advance monthly payment of the family and disability deductions. |
| `145` | irpf / ad_hoc | Comunicación de datos del perceptor de rentas del trabajo a su pagador (art. 88 RIRPF). | `irpf`, `modelo-111` | Employee's declaration of personal and family circumstances to their employer, setting the withholding rate. Given to the payer, not filed with AEAT. |
| `156` | informative / annual | Cotizaciones de afiliados y mutualistas a efectos de la deducción por maternidad. Declaración informativa anual. | `irpf`, `modelo-100` | Annual informativa by social-security bodies reporting contributions that support the maternity deduction. |
| `165` | informative / annual | Declaración informativa de certificaciones individuales emitidas a los socios o partícipes de entidades de nueva o reciente creación. | `modelo`, `declaracion` | Annual informativa by new companies listing the investment certificates issued to their shareholders. |
| `179` | informative / annual | Declaración informativa anual de la cesión de uso de viviendas con fines turísticos. | `modelo`, `declaracion` | Annual informativa by holiday-rental intermediaries reporting tourist-use property lettings. |
| `181` | informative / annual | Declaración informativa de préstamos y créditos, y operaciones financieras relacionadas con bienes inmuebles. | `modelo`, `declaracion` | Annual informativa by lenders on loans, credits, and property-related financial operations. |
| `182` | informative / annual | Declaración informativa de donativos, donaciones y aportaciones recibidas y disposiciones realizadas. | `irpf`, `modelo-100` | Annual informativa by charities reporting donations received, which support the donor's deduction. |
| `185` | informative / monthly | Declaración informativa mensual de cotizaciones de afiliados y mutualistas. | `irpf`, `modelo-100` | Monthly counterpart of the annual contributions informativa. |
| `186` | informative / monthly | Declaración informativa de nacimientos y defunciones. | `modelo`, `declaracion` | Monthly informativa filed by civil registries reporting births and deaths. |
| `187` | cross_tax / annual | Declaración informativa de acciones y participaciones de instituciones de inversión colectiva y resumen anual de retenciones. | `irpf`, `modelo-193` | Annual informativa and withholding summary on collective-investment holdings. |
| `188` | cross_tax / annual | Retenciones e ingresos a cuenta. Rentas del capital mobiliario de operaciones de capitalización y contratos de seguro de vida o invalidez. Resumen anual. | `irpf`, `modelo-193` | Annual withholding summary matching the quarterly `128`. |
| `189` | cross_tax / annual | Declaración informativa anual acerca de valores, seguros y rentas. | `modelo`, `modelo-714` | Annual informativa on securities, insurance and annuities holdings, feeding wealth-tax data. |
| `194` | cross_tax / annual | Retenciones e ingresos a cuenta sobre rendimientos del capital mobiliario y rentas de transmisión o reembolso de activos financieros. Resumen anual. | `irpf`, `modelo-193` | Annual withholding summary on financial-asset income and transfers. |
| `216` | irnr / profile_based | IRNR. Rentas obtenidas sin mediación de establecimiento permanente. Retenciones e ingresos a cuenta. | `modelo-210` | Withholding return for payments to non-residents without a permanent establishment. |
| `220` | is / annual | Impuesto sobre Sociedades. Régimen de consolidación fiscal. Declaración. | `modelo-200`, `modelo-202` | Annual corporate-tax return for a fiscally consolidated group. |
| `222` | is / quarterly | Impuesto sobre Sociedades. Régimen de consolidación fiscal. Pago fraccionado. | `modelo-202`, `modelo-200` | Instalment payment for a fiscally consolidated group, the group counterpart of `202`. |
| `231` | is / annual | Declaración de información país por país (CBC/DAC4). | `modelo-232` | Country-by-country report filed by large multinational groups. |
| `233` | informative / annual | Declaración informativa por gastos en guarderías o centros de educación infantil autorizados. | `irpf`, `modelo-100` | Annual informativa by nurseries reporting childcare fees supporting the maternity deduction increase. |
| `234` | informative / profile_based | Declaración de información de determinados mecanismos transfronterizos de planificación fiscal. | `modelo-232` | DAC6 disclosure of reportable cross-border tax-planning arrangements. |
| `238` | informative / annual | Declaración informativa para la comunicación de información por parte de operadores de plataformas. | `modelo`, `declaracion` | DAC7 informativa by digital-platform operators on their sellers. |
| `270` | informative / annual | Resumen anual de retenciones e ingresos a cuenta. Gravamen especial sobre los premios de determinadas loterías y apuestas. | `irpf` | Annual withholding summary for the lottery-prize levy, the counterpart of `136`. |
| `280` | irpf / annual | Declaración informativa anual de Planes de Ahorro a Largo Plazo. | `irpf`, `modelo-100` | Annual informativa on long-term savings plans and their exemption conditions. |
| `289` | cross_tax / annual | Declaración informativa anual de cuentas financieras en el ámbito de la asistencia mutua (CRS). | `modelo-720`, `modelo-721` | CRS informativa by financial institutions on accounts held by non-residents. |
| `296` | irnr / annual | IRNR. No residentes sin establecimiento permanente. Declaración anual de retenciones e ingresos a cuenta. | `modelo-210` | Annual withholding summary for non-resident payments, the counterpart of `216`. |
| `341` | iva / quarterly | Solicitud de reintegro de compensaciones en el régimen especial de la agricultura, ganadería y pesca. | `iva`, `modelo-303` | Claims reimbursement of the flat-rate compensation paid under the agriculture and fishing IVA regime. |
| `345` | irpf / annual | Planes, fondos de pensiones y sistemas alternativos. Declaración anual de partícipes, aportaciones y contribuciones. | `irpf`, `modelo-100` | Annual informativa by pension funds on members and contributions supporting the IRPF reduction. |
| `361` | iva / ad_hoc | Solicitud de devolución del IVA a empresarios no establecidos en el territorio de aplicación del Impuesto ni en la Comunidad. | `iva`, `modelo-360` | IVA refund claim by traders established outside the EU. |
| `379` | iva / quarterly | Declaración informativa sobre pagos transfronterizos (CESOP). | `iva`, `modelo-349` | CESOP informativa by payment service providers on cross-border payments. |
| `380` | iva / profile_based | Declaración-liquidación. Operaciones asimiladas a las importaciones del IVA. | `iva`, `modelo-303` | Settles IVA on operations treated as imports, such as goods leaving a customs regime. |
| `490` | idsd / profile_based | Impuesto sobre Determinados Servicios Digitales. Autoliquidación. | `autoliquidacion`, `modelo` | Self-assessment of the digital services tax on targeted advertising, intermediation and data transfer. |
| `576` | iedmt / profile_based | Impuesto Especial sobre Determinados Medios de Transporte. Autoliquidación. | `autoliquidacion`, `modelo` | Self-assessment of the registration tax due on first registration of a vehicle, vessel or aircraft. |
| `592` | plastico / profile_based | Impuesto especial sobre los envases de plástico no reutilizables. Autoliquidación. | `autoliquidacion`, `modelo` | Self-assessment of the excise on non-reusable plastic packaging manufactured or acquired. |
| `604` | itf / monthly | Impuesto sobre las Transacciones Financieras. Autoliquidación. | `autoliquidacion`, `modelo` | Monthly self-assessment of the financial transactions tax on acquisitions of listed Spanish shares. |
| `763` | juego / profile_based | Impuesto sobre actividades de juego en los supuestos de actividades anuales o plurianuales. Autoliquidación. | `autoliquidacion`, `modelo` | Self-assessment of the gambling activities tax for annual or multi-year activities. |
| `848` | informative / annual | Comunicación del importe neto de la cifra de negocios. Impuesto sobre Actividades Económicas. | `modelo-840` | Reports net turnover to determine IAE liability and exemption, the companion to the `840` register form. |

Four related cells above name a modelo that is itself unenrolled and therefore
not yet a valid target; each is marked in place and falls back to an id that
exists today. They become usable once the campaign enrols the forms it names, at
which point `117`, `122`, `156`, `185`, `216`, `270` and `296` should be revisited
so the counterpart links point at their real partners.

### Modelos that should not become approved concepts

The narrowing rule was structural, so a form-by-form read was asked for. It
found one clear miss and one judgement call.

`145` should be excluded, and the evidence is already in the tree: it is a member
of `OUT_OF_SCOPE_OBLIGATIONS`, whose recorded reason reads "local IRPF payer
communication, not an AEAT filing/calendar obligation". It is the only one of the
43 already declared out of scope; the registry-backed rule readmitted it because
it happens to carry a registry directory. It is also substantively the odd one
out: the taxpayer hands it to their employer and never files it with AEAT, and it
is approved by a DGT resolución rather than a ministerial orden.

Beyond that, roughly fourteen of the remainder are informativas filed by a
specific regulated institution rather than by this product's taxpayer: `186`
(civil registries), `156` and `185` (mutual and social-security bodies), `181`
(lenders), `187`, `188`, `194`, `280` and `345` (fund managers, insurers, pension
funds), `231` (groups above the country-by-country threshold), `289` (financial
institutions under CRS), `238` (platform operators), `379` (payment service
providers), `233` (nurseries). An autónomo or PYME will never file these.

That is not by itself a reason to exclude them, and the recommendation is to keep
them. The Handbook already approves `180`, `184`, `190`, `193`, `347` and `349`,
which are informativas too, and a taxpayer who receives a certificate under `187`
or a donation receipt under `182` has a genuine reason to look the form up. The
glossary rule asks for taxpayer- or operator-facing concepts, and a form whose
data lands in the taxpayer's own Renta qualifies on the receiving side even when
they are not the filer. The distinction worth drawing in the prose is filer
versus recipient, not inclusion versus exclusion.

### What this document does not settle

The three mis-attributed citations and the five framework-only ones are reported,
not repaired. Correcting them means choosing a provision per form and verifying
it, which is the curation step itself and carries the correctness hazard the
campaign has been careful about. Candidate approving órdenes for `187`, `188`,
`194`, `296` and `345` do exist in the bundled corpus, but identifying which one
governs each form is a per-form read, and a plausible-looking orden that amends
rather than approves would be exactly the wrong answer.

The mis-attribution also exposes something structural worth recording: the
evidence gate checks that a citation's `required_text` appears in its
`corpus_ref` file, which cannot detect a correct quotation attached to the wrong
modelo. `187`, `188` and `194` pass the gate today while citing an article that
approves a different form. A gate comparing the citing modelo's number against
the approving text would have caught all three.
