---
tags:
  - '#plan'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-06'
body_hash: 'sha256:0e43769c1a0aab5d78b10e1351ea9c0e5bfde48686b4631e8593ed7e0b687752'
tier: L2
related:
  - '[[2026-08-05-ledger-invoice-decomposition-adr]]'
  - '[[2026-08-05-ledger-invoice-decomposition-reference]]'
  - '[[2026-08-05-ledger-invoice-decomposition-research]]'
---

# `ledger-invoice-decomposition` plan

## Steps

### Phase `P01` - Income measure grounding

Make the renta income measure explicit and its gaps visible. The fact selector stops defaulting to a legal claim, the honest name replaces the misleading one, and every row that reaches a filed casilla without invoice substrate surfaces an advisory instead of folding bank cash in silently.

- [x] `P01.S01` - Remove the fact default from the renta ledger income selector so an omitting binding fails registry validation loudly; `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`.
- [x] `P01.S02` - Remove the divergent fact default from the impatriado income selector so both siblings are required; `src/cadrumo/domain/calculations/registry/_ledger_impatriado_bindings.py`.
- [x] `P01.S03` - Rename the renta and impatriado fact gross_income_sum to cash_received_sum, leaving the accurately-named Modelo 210 member untouched; `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`.
- [x] `P01.S04` - Add the income-side missing-substrate issue reason mirroring the gasto pipeline, with an explicit observation grounding marker; `src/cadrumo/application/aggregation/_renta_income_ledger.py`.
- [x] `P01.S05` - Surface the missing-substrate advisory on both the preflight and calculate paths through the typed notice channel; `src/cadrumo/application/modelo/_calculation_actions.py`.
- [x] `P01.S06` - Stop taxable_base_sum coercing a missing base to zero, routing base-less rows into the ungrounded class; `src/cadrumo/domain/calculations/registry/_ledger_bindings.py`.

### Phase `P02` - Component axis and legal grounding

Declare which components an invoice of each IVA category actually has, as registry-grounded data derived from the existing category frozensets rather than a parallel list that can disagree with them. Land the legal catalogue entries and retencion rate parameters the table cites.

- [x] `P02.S07` - Declare the per-category component-expectation table as registry-grounded data derived from the existing cuota-less frozensets, never a parallel list; `src/cadrumo/domain/iva/_schema.py`.
- [x] `P02.S08` - Gate the table for completeness across every IvaCategory member and for non-divergence from the frozensets it derives from; `src/cadrumo/domain/iva/tests`.
- [x] `P02.S09` - Land the legal catalogue entries every component-expectation row cites, each resolving to bundled authoritative corpus text; `src/cadrumo/_data/registry/aeat/legal`.
- [x] `P02.S10` - Land the RIRPF article 95 retencion rate parameters as registry data rather than feature-module literals; `src/cadrumo/_data/registry/aeat/legal`.
- [x] `P02.S18` - Re-key the component-expectation table on the category and invoice-kind pair, declaring the retencion role per row so an issued credit and a received liability stop sharing a shape; `src/cadrumo/domain/iva/_components.py`.
- [x] `P02.S19` - Reconcile the rich-invoice IvaRate enum against the registry rate table, closing the missing members rather than leaving a rate the registry knows and the record cannot express; `src/cadrumo/domain/invoices/_models.py`.
- [x] `P02.S21` - Bundle the place-of-supply articles governing cross-border category selection, so the judgement is grounded rather than derived from counterparty country; `src/cadrumo/_data/corpus/normatives/html`.
- [x] `P02.S27` - Correct the six-entry LIVA batch document_id to its BOE identifier as one coherent change, then hand it to the operator for re-stamp; `src/cadrumo/_data/registry/aeat/legal`.

### Phase `P03` - Retencion derivation and invoice contracts

Let exempt invoices recover their retencion by relaxing the inference precondition to category-determinable cuota, keeping the registry max-rate bound and never inverting a rate from cash. Give the invoice record its decomposition contract so a partial declaration is excluded but visible.

- [x] `P03.S11` - Relax the withheld-inference precondition to category-determinable cuota so exempt invoices recover their retencion, keeping the registry max-rate bound; `src/cadrumo/application/aggregation/_renta_income_ledger.py`.
- [x] `P03.S12` - Add the invoice retencion consistency validator, holding retencion outside the grand total; `src/cadrumo/domain/transactions`.
- [x] `P03.S13` - Add the partial-invoice decomposition contract so an ungrounded record is excluded but visible rather than silently dropped; `src/cadrumo/domain/transactions`.
- [x] `P03.S20` - Route received-invoice retencion into the existing per-perceptor store behind retenciones_aggregation, never a second parallel retencion path; `src/cadrumo/application/aggregation`.
- [x] `P03.S37` - Let an invoice record that its customer is under recargo de equivalencia, so an unrecorded surcharge stops being indistinguishable from one that does not apply; `src/cadrumo/domain/invoices/_models.py`.
- [x] `P03.S38` - Let the income aggregation read a linked sales invoice for its base, cuota and retencion, following the derive-on-read shape the expense pipeline already proves; `src/cadrumo/application/aggregation/_renta_income_ledger.py`.
- [x] `P03.S39` - Let a general-regime row carry its art. 75 devengo date, so IVA stops being attributed to the bank movement date for the one regime whose law binds it to the operation date; `src/cadrumo/domain/transactions/_models.py, src/cadrumo/domain/transactions/_dates.py, src/cadrumo/application/aggregation/_iva_ledger.py`.

### Phase `P04` - Verify severity escalation

Escalate the missing-substrate advisory to a verify-stage refusal only where the under-declaration direction is certain, on operator ratification.

- [ ] `P04.S14` - Escalate the advisory to a verify-stage refusal only for a row declaring a cuota-less category with no taxable base, pending operator ratification; `src/cadrumo/application/modelo`.
- [ ] `P04.S36` - Decide whether the external-grounding gate admits bound casillas, since a bound value is as oracle-checkable as a computed one, before amending the S15 and S16 Step texts; `.vault/adr`.

### Phase `P05` - Oracle grounding and roundtrip coverage

Prove the chain against external AEAT authority rather than against itself, anchored on a worked example carrying retencion and an exempt-services example, with roundtrip coverage for every new persisted field.

- [ ] `P05.S15` - Ground the chain on an AEAT worked example carrying retencion, asserting against the published figure and never against the formula under test; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `P05.S16` - Ground the chain on an exempt-services example proving the under-declaration direction is closed; `src/cadrumo/domain/calculations/registry/tests`.
- [ ] `P05.S17` - Add strict roundtrip coverage for every new persisted field, with an anti-tautology proof that a deleted field is refused on load; `src/cadrumo/application/calculations/tests`.
- [x] `P05.S22` - Prove one well-formed ledger invoice surfaces consistently in renta income, retenciones and IVA together in a single scenario, with the three figures reconciling to the same decomposition; `src/cadrumo/application/aggregation/tests`.
- [x] `P05.S23` - Prove an ambiguous or incomplete invoice is excluded from all three domains WITH a visible advisory, never silently dropped and never silently folded; `src/cadrumo/application/aggregation/tests`.
- [x] `P05.S24` - Prove each cross-domain assertion fails when the code is wrong, by mutating the decomposition and confirming the scenario reddens rather than passing vacuously; `src/cadrumo/application/aggregation/tests`.
- [x] `P05.S25` - Gate every advisory message builder as constructible at zero, one and many items against its own model's declared cap, read from the field rather than restated; `src/cadrumo/tests`.
- [x] `P05.S26` - Name the dropped retencion credit in the ungrounded advisory, not only the income mis-measurement, since the lost credit is the larger half of the harm; `src/cadrumo/application/aggregation/_modelo_bindings.py`.
- [x] `P05.S28` - Drive a received invoice through to the committed Modelo 111 binding values, asserting the filed casillas against the invoice figures rather than stopping at the aggregation totals; `src/cadrumo/application/aggregation/tests/test_invoice_retencion_routing.py`.
- [x] `P05.S29` - Drive the same invoice through to the committed Modelo 303 repercutido bindings so the IVA leg reaches a filed casilla like the income and retenciones legs already do; `src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py`.
- [x] `P05.S30` - Reconcile the duplicated binding-level assertions between the cross-domain scenario and the rated oracle module, keeping one owner for the shared claim; `src/cadrumo/application/aggregation/tests/test_cross_domain_invoice_scenario.py`.
- [x] `P05.S31` - Read the statutory retencion rate from the registry general_rate at every oracle expectation site, reserving the bound accessor for assertions genuinely about the inference cap; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `P05.S32` - Add a sub-cap oracle case on the 7 percent inicio-de-actividad registry rate so the bound is calibrated at more than one point; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `P05.S33` - Extract the shared oracle fixture scaffolding while keeping each test body separate, so a scenario change lands once; `src/cadrumo/domain/calculations/registry/tests`.
- [x] `P05.S34` - Bundle the PGC norms cited in the oracle docstrings, or mark them not-yet-bundled so the citation stops asserting grounding it lacks; `src/cadrumo/_data/corpus/normatives/html`.
- [x] `P05.S35` - Restore the marker integrity the two campaign-owned test modules broke, so the marker gate stops reporting a campaign surface as unclassified; `src/cadrumo/domain/iva/tests/test_component_expectations.py`.
