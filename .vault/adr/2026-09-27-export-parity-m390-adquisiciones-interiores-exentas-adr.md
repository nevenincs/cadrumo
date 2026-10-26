---
tags:
  - '#adr'
  - '#export-parity'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:c557224f6837cf271d99b679e9f6cdffe634c59a7e33f4bad2a009976b744d25'
related:
  - "[[2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research]]"
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
  - "[[2026-07-11-article-20-uno-26-correction-adr]]"
  - "[[2026-09-09-registry-edition-authoring-adr]]"
---
# `export-parity` adr: `m390 adquisiciones interiores exentas` | (**status:** `accepted`)

## Problem Statement

Modelo 390 box [230] "Adquisiciones interiores exentas" has no binding on any revision. It is a manual casilla that nobody fills. An autonomo's exempt insurance premiums, loan interest and similar acquisitions therefore reach the annual fichero as zeros, and only a non-blocking `unrouted_declarable_quantity` advisory says otherwise. The box is ledger-derived: Modelo 303 has no equivalent box, and DGT V2503-16 says exempt acquisitions go to [230] and never to the 303. The ledger already produces the observations. The binding is missing, and so is a trustworthy way to tell exempt purchases from not-subject ones. Grounding: `2026-09-27-export-parity-m390-adquisiciones-interiores-exentas-research`.

A decision is needed now. The export-parity lanes export Modelo 390 for 2022 to 2025 over a seed that holds an exempt premium every year, and two other efforts are about to edit the same 390 revision files.

## Considerations

- The official definition covers art. 20 exempt acquisitions of goods and services, plus 0 % acquisitions in the 2024 and 2025 editions. The 2022 and 2023 editions are not in hand (research, "official definition").
- In the supported designs, a 0 % interior purchase has no deducible-base box, so in 2024 and 2025 [230] is its only annual home (research, same finding).
- AEAT's own worked example declares an exempt insurance invoice in [230] at the amount billed. It is an independent official oracle for the exempt half (research, "An AEAT worked example").
- Exempt insurance and bank receipts are not invoices and stay outside the SII register, so the ledger row is the only source for them (research, "outside the SII register").
- The IPS law keeps the insurance premium tax (IPS) and the Consorcio and CLEA surcharges out of the premium, and the LIVA folds other taxes into an amount only for operaciones gravadas. No AEAT or DGT text applies either to [230] in so many words (research, "No official source settles").
- Not subject is not exempt. RETA quotas, taxes and owners' community dues stay out (research, "Not subject is not exempt").
- A dwelling let used partly as an office is subject and not exempt. It contributes nothing to [230], and the expense category that records it carries an exempt hint (research, "A dwelling let used partly as an office").
- The ledger records an exempt purchase with an unreduced base but with the `zero` rate tier. A 0-rate row without an explicit category is read as a taxable 0 % purchase. The expense catalogue's only IVA hint merges exempt with not subject and is consumed by no code (research, "Cadrumo records an exempt purchase today").
- An empty match resolves to 0, so the value alone cannot separate "none" from "unclassified" (research, "No binding draws the base today").
- The operator answered the open questions on 2026-09-27: partial business use, classification defaults, advisory severity, population years, DGT consultas in the corpus, the home of the fact 0098 correction, and the refund follow-on. The answers are recorded as the kept options below.
- The accepted silent-zero boundary lets a bounded mirror of an existing ledger aggregation ship through registry wiring alone, and requires an ADR for a new classification axis (`2026-06-19-silent-zero-base-aggregation-adr`). The binding is the mirror. The classification repair and the business-share quantity are the ADR-scale parts.
- One aggregation mechanism per calculation type (`2026-06-10-calculation-aggregation-taxonomy-adr`). The exemption-article discriminator is governed by `2026-07-11-article-20-uno-26-correction-adr`, whose amendment of 2026-09-27 corrects the 8º and 14º descriptions. Authoring is edition-relative, with deltas against a storage baseline (`2026-09-09-registry-edition-authoring-adr`).

## Considered options

- **Population years.**
  - A, exempt only in every year: rejected. It drops 0 % purchases that have no other 2024 or 2025 box.
  - C, exempt plus 0 % in every year: rejected. It asserts wording for 2022 and 2023 that no captured source shows.
  - B, exempt in every year plus 0 % where the captured edition says so: kept, and fixed by the operator on 2026-09-27. Exempt purchases bind from the 2022 baseline. The 0 % part is added from 2024, the first year whose official instructions the corpus holds once L1 captures them. 0 % purchases dated in 2022 and 2023 raise an advisory.
- **Data source.**
  - A `previous_filing` fold of the 303: impossible, because the 303 has no box.
  - Keeping [230] manual: rejected. It is the silent zero this record exists to remove.
  - `ledger_iva_aggregation`: kept, as the one mechanism the 390's other ledger boxes use.
- **Rate tier.**
  - Change the ledger so that `domestic_exempt` resolves to the `exempt` tier before binding: deferred as a separate correctness fix.
  - Admit `zero` and `exempt` in the selector, as Modelo 303 casillas 59 and 60 do: kept.
- **Exemption-article filter on the binding.** Rejected. [230] takes every art. 20 exemption, and no surface sets the discriminator.
- **Amount under partial business use.**
  - The unreduced base the observation already carries: rejected by the operator on 2026-09-27.
  - The business share of the base, from the ledger row's business percentage: kept (operator decision). No official text addresses the share for exempt acquisitions (research). It needs a business-share base quantity, because the 303 and 390 deducible bases must stay unreduced ("sin prorratear").
- **Insurance premium tax and surcharges in the amount.**
  - The premium alone, without the IPS and the Consorcio and CLEA surcharges, with a non-blocking advisory on every contributing insurance row until an AEAT or DGT text confirms it: kept (operator decision, 2026-09-27). The [230] instruction asks for the amount of the exempt acquisition itself; Ley 13/1996 art. 12.Ocho.b) defines the premium as the consideration for the insurance operation, excluding the surcharges and the taxes that fall on it; and art. 12.Diez makes the IPS a tax passed on like the IVA.
  - The full amount charged, taxes and surcharges included: rejected. LIVA art. 78.Dos.4º adds other taxes to an amount only for operaciones gravadas, and no text brings into an exempt acquisition a tax the IPS law keeps out of the premium.
- **Classification of inputs.**
  - Operator declaration only, plus an advisory: rejected on its own. It leaves the misreading of a bare 0 rate in place.
  - Model inference: rejected. It is a filing-bound default without legal authority.
  - Typed category hints, with a registry-declared default art. 20 sub-article for clearly exempt categories and refusal for ambiguous ones until the operator declares them: kept (operator decision).
- **Severity of the unclassified-candidate issue.** Blocking filing-grade verification: rejected by the operator. The issue is an advisory that is stored and shown in verify, the handoff and the report.
- **Citing DGT consultas.** Citing them as `other` or as AEAT guidance: rejected. A corpus source kind of their own: kept (operator decision), built in L1.
- **Fact 0098 description correction.** Under this record: rejected. The operator decided it by amending `2026-07-11-article-20-uno-26-correction-adr`. This record only adds members.
- **Refunds.** The L5 rectification model stays a follow-on (operator decision).
- **303 residual advisory.** Reclassifying it in Python as "declared on the annual return" was rejected, because it couples the modelos outside the registry. The advisory stays accurate and unchanged.

## Constraints

- Filing-grade grounding (`aeat-calculation-grounding`):
  - The exempt half rests on LIVA art. 20, on the record designs' label in every supported year, on DGT V2503-16, and on AEAT's worked example.
  - The 0 % half is grounded from 2024, once L1 captures the 2024 and 2025 instruction PDFs. 2022 and 2023 carry the 0 % advisory instead of a value.
  - A DGT consulta enters the registry only through the source kind L1 adds, read from the DGT's own service. V0291-20 was read in a third-party copy and must be re-read before it is cited.
  - The IPS rule rests on Ley 13/1996 art. 12.Ocho.b) and 12.Diez, LIVA art. 78.Dos.4º and the [230] instruction. No AEAT or DGT text applies it to [230] in so many words, so insurance rows keep a non-blocking advisory until one does.
- Missing, unclassified and zero stay distinct (`no-silent-under-declaration`, `aeat-registry-bindings`). The binding adds no zero coercion beyond the family's existing empty-match semantics, and no advisory changes a bound value.
- Registry authority flow (`aeat-registry-authority-flow`):
  - Delta authoring only, against the 2022 storage baseline.
  - The construct's positional `sequence_order` vectors in 2023, 2024 and 2025 must be recomputed through the canonical converter, never hand-edited.
  - One writer for the 390 revision, bindings, casillas and constructs files, sequenced with the `S13` conformance rectification in `2026-09-26-export-parity-plan` and with the sibling investment-goods binding work.
- Ledger contract (`aeat-ledger-contract`):
  - Amounts stay non-negative magnitudes, and a refund must be a typed rectification, never a negative base.
  - The business share derives from the row's existing business percentage. No second percentage is stored.

## Implementation

Proposed, and not to be executed before operator acceptance. It is layered, so the binding can land before the classification repair, provided the advisories land with it.

**L1, grounding.**
- Capture the two official instruction PDFs through the corpus route used for `aeat-modelo-190-instructions-2025`:
  - the 2025 edition, `Instrucciones_modelo_390-2025.pdf`;
  - the 2024 edition, `instr390.pdf`.
- Place them under `corpus/aeat_official/instructions/modelo_390/files/`, enroll them in `src/cadrumo/_data/registry/aeat/legal/iva.toml` as `aeat-modelo-390-instructions-2025` and `-2024` with receipts and applicability, and generate their text sidecars.
- Add a corpus source kind for DGT consultas vinculantes. It is described here and not built under this record's acceptance alone:
  - a legal-reference kind `consulta_vinculante`, and a publishing authority `dgt`, because neither the BOE nor the AEAT publishes the consultas;
  - evidence tier `official_source_guidance`. A consulta binds the Administration's application bodies (LGT art. 89.1, `src/cadrumo/_data/corpus/normatives/html/ley-58-2003.html.extracted.md:937-939`) but is not law, so a filing-grade value still needs the statute or instruction the consulta applies. The tier's description widens from AEAT guidance to official administrative guidance;
  - identity fields: consulta number (`Vnnnn-yy`), fecha de salida, órgano, the normativa it cites, the DGT service URL, retrieval date, and the sha256 and size of the captured text, with a text sidecar like other corpus captures;
  - a capture script beside `dev/corpus/fetch_boe_normative.py`, identity fields in `dev/registry/compiler/corpus_catalogue.py`, and catalogue validation for the new kind with positive, refusal and detector tests;
  - first members: V2503-16 (exempt acquisitions go to [230]) and V0291-20 (mixed-use dwelling let).
- Capture Ley 13/1996 art. 12 through the BOE normative route, so the IPS rule and its advisory can cite it.
- Capture AEAT's filled Modelo 390 for the Manual práctico worked example, 2024 edition, as the evidence behind the test oracle.

**L2, binding.**
- Add a fact to the `ledger_iva_aggregation` family: `business_share_base_amount_sum`. The observation carries the row's base multiplied by the same business proportionality that already scales its cuota, with the family's existing money rounding. The fact is enrolled in the family's fact dispatch and selector validation. The existing `base_amount_sum` bindings keep the unreduced base.
- Add one binding, `modelo-390-especificas-adquisiciones-interiores-exentas-base`, to the 2022 bindings fragment. Its provider:
  - kind `ledger_iva_aggregation`;
  - categories `domestic_exempt`;
  - rate kinds `zero` and `exempt`;
  - flow `soportado`;
  - fact `business_share_base_amount_sum`;
  - observation role `settlement`;
  - the same three cash-accounting treatments as its siblings;
  - no `applied_rates`, and no `exemption_articles` filter.
- Its value is money, aggregated by `sum`. Its legal refs are `ley-37-1992:art-20`, `rd-1624-1992:art-71` and `orden-eha-3111-2009:art-1`.
- The native 2022 casilla row gains `input_kind = "bound"` and the binding. The construct `modelo-390-iva-resumen-anual` gains the casilla and the binding. The derived completeness manifest is regenerated.
- 2023 inherits unchanged.
- 2024 carries a `family_overrides` patch on that binding. The patch adds `domestic_zero` to its categories and cites the 2024 instructions. 2025 inherits it and adds only its own source identity.
- Moving the 0 % patch below 2024, should a 2022 or 2023 edition be captured with the same wording, is an amendment of this record.
- The change goes through `dev.registry.edition_delta_migration` and `registry_collapse_verification`. The page-7 export targets are regenerated and checked. Authority is published only when the operator asks.

**L3, visibility.** Every issue here is a non-blocking source issue on the existing `CalculationSourceIssue` channel. It is stored on the calculation revision and shown in verify, the export handoff and the calculation report. None blocks filing-grade verification. Each names the modelo, revision, casilla 230, binding, ledger ids, category and reason.
- Unclassified exempt-acquisition candidate: a received business row in an exempt-hinted expense category did not reach [230], because it settled under another category or was refused by a missing-fact gate.
- 0 % purchase before the 0 % wording: a received `domestic_zero` row dated in 2022 or 2023. It replaces the generic advisory for that row.
- Insurance premium rule pending confirmation: a row in an insurance category, or declared under 16º, contributed its premium to [230], without the IPS and the Consorcio and CLEA surcharges. The advisory stays until an AEAT or DGT text confirms the rule; confirmation removes it without changing the value.
- Receipt components: an insurance row's taxable base is the premium. The IPS and the surcharges are recorded as separate typed amounts on the row, never folded into the base, so the receipt still reconciles with its bank movement and neither reaches a box.
- The 390 `unrouted_declarable_quantity` advisory stops for exempt bases and keeps reporting not-subject bases. The 303 advisory is unchanged.

**L4, classification.**
- Split the `exempt_or_non_subject` hint in fact 0064 into typed hints `exempt`, `exempt_conditional` and `not_subject`. `general` and `non_deductible_input` stay. The assignments:
  - `exempt`, with a registry-declared default sub-article: `seguros_responsabilidad_civil`, `seguros_salud_autonomo`, `vehiculo_seguro` and `mutualidad_alternativa` (16º); `gastos_financieros` and `gastos_bancarios` (18º). The bank-fee default follows the operator's decision. Its provenance names the 18º carve-outs (collection management, factoring services to the assignor, custody and management of securities), and the operator records such a fee with its explicit taxed category.
  - `exempt_conditional`: `cuotas_colegiales` (12º) and `formacion_profesional` (9º or 10º, by provider).
  - `not_subject`: `cuotas_autonomos_ss`, `ibi_local_afecto`, `ibi_vivienda_afecto`, `tributos_fiscalmente_deducibles`, `comunidad_vivienda_afecto`, `amortizacion_vivienda_afecto` and `manutencion_dietas_extranjero`.
  - `general`: `arrendamiento_vivienda_afecto`, because a mixed-use dwelling let is subject and not exempt, and `manutencion_dietas_nacional`.
- In the shared ledger application service, used by the CLI and the TUI:
  - A received business row with a 0 rate and no explicit IVA category in an `exempt` category settles as `domestic_exempt` with the default article, carrying visible "expense-category default" provenance.
  - In an `exempt_conditional` or `not_subject` category, the same row is refused with a message naming the category to declare.
  - In `arrendamiento_vivienda_afecto`, the same row is refused with the mixed-use reason, and an explicit `domestic_exempt` is refused as well. The category itself records the partial business use that defeats 23º.b.
  - Elsewhere, an explicit category that contradicts the hint raises an advisory, not a refusal.
- Add `--exemption-article` to the ledger commands that accept `--iva-category`. It is validated against fact 0098 and refused unless the category is `domestic_exempt`.
- Extend the fact 0098 vocabulary with members for 1º, 3º, 9º, 10º, 12º, 16º, 18º, 22º and 23º. The 8º and 14º descriptions are corrected under the amendment of `2026-07-11-article-20-uno-26-correction-adr`. This stays a provenance axis; no box routes on it.
- New messages go through `dev.locales` for every supported locale.

**L5, rectification (follow-on).** A typed rectification identity for cuota-less received rows, with a linked ledger id and a signed evidence amount under the contract's direction field, so a refund nets inside the same aggregation. Until it exists, the candidate issue covers any refund the operator cannot record.

**Export and surfaces.**
- The fichero writes the bound value at page 7, offset 13. The field is signed type N, so a net negative takes the design's "N" prefix. The layout itself does not change.
- The offline XLSX, the CSV casilla table and the calculation-summary PDF show [230] with its binding provenance, the matched ledger ids and every L3 issue through the existing report builder.
- The CLI and TUI calculate, explain and export surfaces need no new command. The new surfaces are ledger-side only (L4).

**Tests.** All run over the real compiled registry and resolver, with synthetic data only.
- Hand arithmetic for 2025:
  - Inputs: a 480.00 civil-liability premium receipt (440.00 premium, 35.20 IPS, 4.80 surcharges; `domestic_exempt`, 16º, fully business); 120.00 of loan interest (`domestic_exempt`, 18º, fully business); a 300.00 vehicle premium at 50 % business use; twelve RETA quotas of 300.00 (`operacion_no_sujeta`); 250.00 of IBI (`domestic_not_subject`); a 200.00 + 42.00 taxable purchase (`domestic_general`); a 1,000.00 + 210.00 mixed-use dwelling let at 30 % business use (`domestic_general`); and a 1,000.00 exempt sale on the issued side.
  - Result: [230] = 440.00 + 120.00 + 150.00 = 710.00. The 480.00 receipt contributes its 440.00 premium; its 35.20 IPS and 4.80 surcharges reach no box. The insurance-rule advisory names both insurance rows. The taxable purchase and the dwelling let reach the soportado route with unreduced bases, and the exempt sale reaches neither [230] nor any soportado box.
- A 2024 case adds a 50.00 purchase at 0 %, dated in the first half of the year: [230] = 760.00. The same row in 2023 stays out of [230] and raises the 0 % issue.
- AEAT oracle: the worked example's exempt 500.00 insurance invoice yields [230] = 500.00, as AEAT's filled form prints. The existing 2024 manual oracle for that example gains the casilla.
- Exclusion cases, each alone yielding [230] = 0.00 with provenance:
  - not subject, RETA, a deductible taxed purchase, a mixed-use dwelling let;
  - an intra-Community acquisition at 0 %, a REAGP compensation;
  - an issued exempt sale, a PERSONAL row.
- Business share: a mixed row contributes its business share; a half-cent share follows the family's money rounding; the 303 deducible bases of the same ledger stay unreduced.
- Missing-data and refusal cases:
  - an exempt-hinted row lacking its taxable base yields the gate issue plus the candidate issue;
  - a 0-rate row without a category in a conditional category is refused at the CLI;
  - a 0-rate row, or an explicit `domestic_exempt`, in `arrendamiento_vivienda_afecto` is refused.
- A genuine-zero year with every purchase classified and none exempt yields 0.00 and no candidate issue.
- 303-to-390 parity: the business-share exempt bases of the four 303 quarterly observation sets sum to the 390 [230] total from the same ledger, and every 303 quarter declares none of it.
- The DGT source kind: a well-formed consulta entry validates, and an entry without its number or date is refused.
- The existing test that asserts no box draws the premium on either form is rewritten to the new truth. The fichero page-7 parse round-trips 710.00. Locale completeness covers the new keys.

## Rationale

The binding reuses the one aggregation family and the observations the ledger already builds, so the 303 and 390 read identical rows with no second summation path. That is the bounded-mirror case in `2026-06-19-silent-zero-base-aggregation-adr`. The business share is the operator's rule. It adds one fact to the same family and derives from the proportionality that already scales the cuota, so the percentage lives in one place and the deducible bases keep their unreduced convention.

Option B, with the operator's 2024 start, neither asserts unseen evidence nor drops 0 % purchases that have no other home. It keeps the unproven years advisory rather than guessed. Admitting both rate tiers follows an existing selector precedent and needs no ledger migration.

The IPS rule follows the statutes. Ley 13/1996 art. 12.Ocho.b) defines the premium as the consideration for the insurance operation, excluding the surcharges and the taxes that fall on it; art. 12.Diez makes the IPS a tax passed on like the IVA; LIVA art. 78.Dos.4º adds other taxes to an amount only for operaciones gravadas; and the [230] instruction asks for the amount of the exempt acquisition itself. No AEAT or DGT text applies this to [230] in so many words, so the advisory keeps the point visible until one does. The dwelling rule follows AEAT's published guidance and DGT V0291-20, which leave no exempt amount to declare.

The classification layer is justified because the value is only as good as the category the operator records. Today a bare 0 rate becomes a taxable purchase, and the expense hint that could catch it merges exempt with not subject and marks a taxed let as exempt (research, "Cadrumo records an exempt purchase today" and "A dwelling let used partly as an office").

## Consequences

- The annual fichero declares the business share of exempt acquisitions for every supported year. The quarterly 303 keeps its accurate advisory.
- Taxpayers with 0 % purchases in 2022 and 2023 see an advisory instead of a value.
- Every return with an insurance premium carries the insurance-rule advisory until an AEAT or DGT text confirms it; confirmation removes the advisory without changing [230].
- A taxed bank service recorded without an explicit category is defaulted to exempt. The default's provenance shows it, and an explicit category corrects it.
- The construct and edition edits collide with two concurrent 390 efforts, so the work waits for a single writer.
- L4 changes operator-facing ledger behaviour: some previously accepted 0-rate rows are now refused, among them every 0-rate dwelling-let row. Rows already stored are surfaced by L3 rather than rewritten.
- The DGT source kind extends the registry's legal-reference schema, the corpus catalogue and the catalogue validation.
- The same mechanism opens [109], [113], [523] and [654] to [657], and the supply-side [105], as follow-ons. [231] and [232] need new ledger quantities first.
- Settled by the operator on 2026-09-27: [230] takes the premium alone, without the IPS and the Consorcio and CLEA surcharges, with a non-blocking advisory until an AEAT or DGT text confirms it. No operator question remains.
