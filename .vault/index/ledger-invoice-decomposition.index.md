---
generated: true
tags:
  - '#index'
  - '#ledger-invoice-decomposition'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:6df0e3d03c9f2ec10f255eca7153bb4b663e4ca58ee90ff74f36e5fb46ed6f2d'
related:
  - '[[2026-08-05-ledger-invoice-decomposition-adr]]'
  - '[[2026-08-05-ledger-invoice-decomposition-loader-fingerprint-format-trap-audit]]'
  - '[[2026-08-05-ledger-invoice-decomposition-plan]]'
  - '[[2026-08-05-ledger-invoice-decomposition-reference]]'
  - '[[2026-08-05-ledger-invoice-decomposition-research]]'
  - '[[2026-08-06-ledger-invoice-decomposition-iva-deduction-ratio-producer-research]]'
  - '[[2026-08-07-ledger-invoice-decomposition-catalogue-surface-conflict-audit]]'
---

# `ledger-invoice-decomposition` feature index

Auto-generated index of all documents tagged with `#ledger-invoice-decomposition`.

## Documents

### adr

- `2026-08-05-ledger-invoice-decomposition-adr` - `ledger-invoice-decomposition` adr: `Invoice decomposition and income grounding` | (**status:** `proposed`)

### audit

- `2026-08-05-ledger-invoice-decomposition-loader-fingerprint-format-trap-audit` - `ledger-invoice-decomposition` audit: `loader fingerprint format trap`
- `2026-08-07-ledger-invoice-decomposition-catalogue-surface-conflict-audit` - `ledger-invoice-decomposition` audit: P06.S55 targets a surface another campaign is retiring

### exec

- `2026-08-05-ledger-invoice-decomposition-P01-S01` - Remove the fact default from the renta ledger income selector so an omitting binding fails registry validation loudly
- `2026-08-05-ledger-invoice-decomposition-P01-S02` - Remove the divergent fact default from the impatriado income selector so both siblings are required
- `2026-08-05-ledger-invoice-decomposition-P01-S03` - Rename the renta and impatriado fact gross_income_sum to cash_received_sum, leaving the accurately-named Modelo 210 member untouched
- `2026-08-05-ledger-invoice-decomposition-P01-S04` - Add the income-side missing-substrate issue reason mirroring the gasto pipeline, with an explicit observation grounding marker
- `2026-08-05-ledger-invoice-decomposition-P01-S05` - Surface the missing-substrate advisory on both the preflight and calculate paths through the typed notice channel
- `2026-08-05-ledger-invoice-decomposition-P01-S06` - Stop taxable_base_sum coercing a missing base to zero, routing base-less rows into the ungrounded class
- `2026-08-05-ledger-invoice-decomposition-P02-S07` - Declare the per-category component-expectation table as registry-grounded data derived from the existing cuota-less frozensets, never a parallel list
- `2026-08-05-ledger-invoice-decomposition-P02-S08` - Gate the table for completeness across every IvaCategory member and for non-divergence from the frozensets it derives from
- `2026-08-05-ledger-invoice-decomposition-P02-S09` - Land the legal catalogue entries every component-expectation row cites, each resolving to bundled authoritative corpus text
- `2026-08-05-ledger-invoice-decomposition-P02-S10` - Land the RIRPF article 95 retencion rate parameters as registry data rather than feature-module literals
- `2026-08-05-ledger-invoice-decomposition-P02-S18` - Re-key the component-expectation table on the category and invoice-kind pair, declaring the retencion role per row so an issued credit and a received liability stop sharing a shape
- `2026-08-05-ledger-invoice-decomposition-P02-S19` - Reconcile the rich-invoice IvaRate enum against the registry rate table, closing the missing members rather than leaving a rate the registry knows and the record cannot express
- `2026-08-05-ledger-invoice-decomposition-P02-S21` - Bundle the place-of-supply articles governing cross-border category selection, so the judgement is grounded rather than derived from counterparty country
- `2026-08-05-ledger-invoice-decomposition-P02-S27` - Correct the six-entry LIVA batch document_id to its BOE identifier as one coherent change, then hand it to the operator for re-stamp
- `2026-08-05-ledger-invoice-decomposition-P03-S11` - Relax the withheld-inference precondition to category-determinable cuota so exempt invoices recover their retencion, keeping the registry max-rate bound
- `2026-08-05-ledger-invoice-decomposition-P03-S12` - Add the invoice retencion consistency validator, holding retencion outside the grand total
- `2026-08-05-ledger-invoice-decomposition-P03-S13` - Add the partial-invoice decomposition contract so an ungrounded record is excluded but visible rather than silently dropped
- `2026-08-05-ledger-invoice-decomposition-P03-S20` - Route received-invoice retencion into the existing per-perceptor store behind retenciones_aggregation, never a second parallel retencion path
- `2026-08-05-ledger-invoice-decomposition-P04-S14` - Escalate the advisory to a verify-stage refusal only for a row declaring a cuota-less category with no taxable base
- `2026-08-05-ledger-invoice-decomposition-P05-S15` - Ground the chain on an AEAT worked example carrying retencion, asserting against the published figure and never against the formula under test
- `2026-08-05-ledger-invoice-decomposition-P05-S16` - Ground the chain on an exempt-services example proving the under-declaration direction is closed
- `2026-08-05-ledger-invoice-decomposition-P05-S17` - Add strict roundtrip coverage for every new persisted field, with an anti-tautology proof that a deleted field is refused on load
- `2026-08-05-ledger-invoice-decomposition-P05-S22` - Prove one well-formed ledger invoice surfaces consistently in renta income, retenciones and IVA together in a single scenario, with the three figures reconciling to the same decomposition
- `2026-08-05-ledger-invoice-decomposition-P05-S23` - Prove an ambiguous or incomplete invoice is excluded from all three domains WITH a visible advisory, never silently dropped and never silently folded
- `2026-08-05-ledger-invoice-decomposition-P05-S24` - Prove each cross-domain assertion fails when the code is wrong, by mutating the decomposition and confirming the scenario reddens rather than passing vacuously
- `2026-08-05-ledger-invoice-decomposition-P05-S26` - Name the dropped retencion credit in the ungrounded advisory, not only the income mis-measurement, since the lost credit is the larger half of the harm
- `2026-08-05-ledger-invoice-decomposition-P03-S37` - Let an invoice record that its customer is under recargo de equivalencia, so an unrecorded surcharge stops being indistinguishable from one that does not apply
- `2026-08-05-ledger-invoice-decomposition-P03-S38` - Let the income aggregation read a linked sales invoice for its base, cuota and retencion, following the derive-on-read shape the expense pipeline already proves
- `2026-08-05-ledger-invoice-decomposition-P03-S39` - Let a general-regime row carry its art. 75 devengo date, so IVA stops being attributed to the bank movement date for the one regime whose law binds it to the operation date
- `2026-08-05-ledger-invoice-decomposition-P04-S36` - Decide whether the external-grounding gate admits bound casillas, since a bound value is as oracle-checkable as a computed one, before amending the S15 and S16 Step texts
- `2026-08-05-ledger-invoice-decomposition-P05-S25` - Gate every advisory message builder as constructible at zero, one and many items against its own model's declared cap, read from the field rather than restated
- `2026-08-05-ledger-invoice-decomposition-P05-S28` - Drive a received invoice through to the committed Modelo 111 binding values, asserting the filed casillas against the invoice figures rather than stopping at the aggregation totals
- `2026-08-05-ledger-invoice-decomposition-P05-S29` - Drive the same invoice through to the committed Modelo 303 repercutido bindings so the IVA leg reaches a filed casilla like the income and retenciones legs already do
- `2026-08-05-ledger-invoice-decomposition-P05-S30` - Reconcile the duplicated binding-level assertions between the cross-domain scenario and the rated oracle module, keeping one owner for the shared claim
- `2026-08-05-ledger-invoice-decomposition-P05-S31` - Read the statutory retencion rate from the registry general_rate at every oracle expectation site, reserving the bound accessor for assertions genuinely about the inference cap
- `2026-08-05-ledger-invoice-decomposition-P05-S32` - Add a sub-cap oracle case on the 7 percent inicio-de-actividad registry rate so the bound is calibrated at more than one point
- `2026-08-05-ledger-invoice-decomposition-P05-S33` - Extract the shared oracle fixture scaffolding while keeping each test body separate, so a scenario change lands once
- `2026-08-05-ledger-invoice-decomposition-P05-S34` - Bundle the PGC norms cited in the oracle docstrings, or mark them not-yet-bundled so the citation stops asserting grounding it lacks
- `2026-08-05-ledger-invoice-decomposition-P05-S35` - Restore the marker integrity the two campaign-owned test modules broke, so the marker gate stops reporting a campaign surface as unclassified
- `2026-08-05-ledger-invoice-decomposition-P06-S40` - Bundle RD 1619/2012 articles 6 and 11 from BOE consolidated text, since only article 2 ships today and article 6 is the authority the schema field set derives from
- `2026-08-05-ledger-invoice-decomposition-P06-S41` - Let the invoice record its fecha de operacion, so the art. 75 devengo date has an authoritative source instead of the issue-date proxy
- `2026-08-05-ledger-invoice-decomposition-P06-S42` - Let the invoice carry a suplido, which joins total and cash while joining neither base nor cuota, taking a third position on the identity rather than a second recargo
- `2026-08-05-ledger-invoice-decomposition-P06-S43` - Let a factura rectificativa name what it corrects, so the cuota rectification LIVA article 89 requires becomes representable
- `2026-08-05-ledger-invoice-decomposition-P06-S44` - Key the counterparty tax-id requirement to the three cases article 6.1.d enumerates, and in those same cases require a structurally-valid NIF-IVA rather than any tax id, so an intra-community supply stops accepting a domestic number
- `2026-08-05-ledger-invoice-decomposition-P06-S45` - Represent pagos anticipados so a prepayment devengues on collection for the amount received, honouring the article 25 exclusion
- `2026-08-05-ledger-invoice-decomposition-P06-S46` - Wire the invoice decomposition contract to a consumer so its defect verdicts reach an operator, since it classifies nothing today and the aggregation paths each carry their own inline guard set instead
- `2026-08-05-ledger-invoice-decomposition-P06-S47` - Wire route_invoice_retenciones into the invoice lifecycle so a received invoice's retencion reaches Modelo 111, asserting the filed figure moves rather than that the projection returns a value
- `2026-08-05-ledger-invoice-decomposition-P06-S48` - Thread the operation date into period attribution with a declared rank marker naming which source produced it, surfaced identically on the pull and calculate paths
- `2026-08-05-ledger-invoice-decomposition-P06-S49` - Drive one accumulative invoice life through Modelo 303 and 390 and through Modelo 130 and 100 across several periods, asserting the same operation lands in one period on both the quarterly and annual sides
- `2026-08-05-ledger-invoice-decomposition-P06-S50` - Refuse a suite of deliberately degraded invoices, each asserting its own specific refusal rather than that something failed, covering the falsified-total, netted-retencion, contradicted-operation-date, referentless-rectificativa and over-threshold-simplificada cases
- `2026-08-05-ledger-invoice-decomposition-P06-S51` - Bundle RD 1619/2012 art. 4 and refuse a factura simplificada for an entrega intracomunitaria exenta (art. 4.4.a), declaring the amount-threshold and sector-list eligibility axis unverified pending an ADR amendment
- `2026-08-05-ledger-invoice-decomposition-P06-S52` - Carry recargo de equivalencia inside the ledger transaction totals identity, so the substrate Modelo 303 and 130 actually read stops refusing the truthful row and accepting the falsified one
- `2026-08-05-ledger-invoice-decomposition-P06-S53` - Refuse a missing --total-amount on the slim invoice add CLI verb instead of silently defaulting the total to zero, since the total drives whether a counterparty is declared at all under the RD 1065/2007 art. 31 Modelo 347 threshold
- `2026-08-05-ledger-invoice-decomposition-P06-S56` - Join the non-deductible share of a fact's input IVA to the IRPF-deductible cost basis via a new RentaDeductibilityContext.iva_deduction_ratio axis, grounded on the AEAT Manual practico Renta 2024 medico radiologo nota 7 worked example (activity exempt from IVA, no right to deduct), leaving the axis unwired from any production taxpayer-fact source as a named follow-up
- `2026-08-05-ledger-invoice-decomposition-P06-S57` - Wire RentaDeductibilityContext.iva_deduction_ratio to a real producer: a wholly EXENTO iva.regime profile fact resolves to zero, otherwise the bucket's ProrrataRegister whole-entity entry contributes its in-force provisional percentage, mirroring the resolution the M303 side already applies
- `2026-08-05-ledger-invoice-decomposition-P06-S58` - Extend the iva_deduction_ratio wiring to the M130 quarterly gasto path: aggregate_renta_gasto_ledger_from_repositories now resolves the same ratio through the shared _resolve_iva_deduction_ratio, for the same ejercicio, so M130 and M100 cannot diverge on it
- `2026-08-05-ledger-invoice-decomposition-P06-S60` - Reground telefonia_fija to LIRPF art. 30.2.5.b's own suministros enumeration (agua, gas, electricidad, telefonia e Internet), moving it into HOME_OFFICE_SUMINISTROS with the statutory 0.30 multiplier it was missing, since it previously deducted at the raw home-area ratio with no censo-consistency guard
- `2026-08-05-ledger-invoice-decomposition-P06-S61` - Move arrendamiento_vivienda_afecto from PREMISES into HOME_OFFICE_OWNERSHIP as the renter's parallel to amortizacion/ibi/comunidad_vivienda_afecto, correcting its citation from the suministros-only art. 30.2.5.b to the general art. 29.2 partial-affectation doctrine plus art. 28.1, and dropping its stray default_ratio so it now requires an explicit operator ratio like its true siblings
- `2026-08-05-ledger-invoice-decomposition-P06-S55` - Wire simplificada_requires_tax_id_for_domestic_issuer to an operator-facing Notice

### plan

- `2026-08-05-ledger-invoice-decomposition-plan` - `ledger-invoice-decomposition` plan

### reference

- `2026-08-05-ledger-invoice-decomposition-reference` - `ledger-invoice-decomposition` reference: `invoice decomposition and income grounding`

### research

- `2026-08-05-ledger-invoice-decomposition-research` - `ledger-invoice-decomposition` research: `Calculation chain fragmentation across ledger, invoice, modelo and engine`
- `2026-08-06-ledger-invoice-decomposition-iva-deduction-ratio-producer-research` - `ledger-invoice-decomposition` research: `iva_deduction_ratio producer design (open, unresolved)`
