---
tags:
  - '#reference'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:5a6ce86741cf67be3dc0a4e71b43fb6f7d56b3fdeccef47c8303faf765881b69'
related: []
---

# `ledger-invoice-decomposition` reference: `invoice decomposition and income grounding`

Grounding for an ADR on two coupled hardening sites: the ledger ingestion contract for an
invoice, and the calculation backend that decomposes an invoice into the components a modelo
casilla consumes. Findings below were produced during the 2026-08-05 deduplication sweep and
each load-bearing claim was verified twice — once by the discovering agent, once independently
by the coordinator reading the cited site.

Claims are marked MEASURED (read directly at the cited location) or REASONED (domain inference
on a cited framework). No figure in this document is quoted from the bundled corpus without the
distinction being stated.

## The defect that opened the question

MEASURED. A freelancer who imports bank statements, tags rows with an actividad-económica IRPF
category, and never records the invoice behind them has cash-received folded into the income
casilla of a filed modelo.

The chain, each link read at HEAD:

- `RentaIncomeObservation.gross_amount` is `abs(transaction.raw.amount)` —
  `application/aggregation/_renta_income_ledger.py:434`. That is the bank-credited figure.
- No inbound financial adapter populates `taxable_base`. Zero references under
  `adapters/inbound/financial/`; the CSV, OFX, XLSX and N26-PDF providers set raw fields only.
- The `ingresos_integros_sum` fact falls back to `gross_amount` when `taxable_base_amount` is
  `None` — `domain/calculations/registry/_ledger_bindings.py:1003-1012`.

So the income casilla receives cash. For contracted work the payer withholds at source, so that
cash is net of retención.

**The error changes direction with the invoice, which is why no single guard catches it.**
REASONED, on the arithmetic: at 21% IVA with 15% retención the credited cash is 1.06 × base, an
over-declaration of roughly 6% of base. For an IVA-exempt professional service — LIVA art. 20,
e.g. formación — with 15% retención, cash is 0.85 × base: a silent under-declaration of 15% of
base on the return's central figure.

**It compounds in the same rows.** MEASURED: `_income_withheld_amount`
(`_renta_income_ledger.py:459-468`) requires BOTH `taxable_base` and `iva_amount` to infer
withholding. Rows lacking substrate therefore contribute zero to the retenciones casilla. Income
is understated and the offsetting credit is dropped from one missing input.

**It is silent by asymmetry, and this is the sharpest structural finding.** MEASURED: the gasto
pipeline declares `MISSING_TAXABLE_BASE` (`_renta_gasto_ledger.py:88`, raised at `:277`) and the
IVA pipeline carries three references to the equivalent; both surface the row rather than
gross-folding it. The gasto docstring states the reason: IVA soportado is recovered through
Modelo 303 and is not a Renta gasto, so a declarable expense without a base is surfaced instead
of folded. The income pipeline's issue-reason enum has seven members and none covers missing
substrate. **The expense side deliberately refuses exactly the gross-fold the income side
performs.**

When substrate IS recorded the path is correct. MEASURED: the Transaction gross invariant
(`domain/transactions/_models.py:1118-1206`) explicitly accepts net-paid incoming activity rows
where cash is less than base plus IVA, and bounds the inferred withholding by a maximum
supported rate.

## The selector-default question this surfaced

MEASURED. Two sibling selectors default differently for one concept:

- `_RentaLedgerIncomeSelector.fact` defaults to `gross_income_sum` —
  `domain/calculations/registry/_ledger_bindings.py:911-913`.
- `_ImpatriadoLedgerIncomeSelector.fact` defaults to `ingresos_integros_sum` —
  `domain/calculations/registry/_ledger_impatriado_bindings.py:101`.
- `_IrnrLedgerIncomeSelector.fact` has `gross_income_sum` as its sole Literal member
  (`_irnr_ledger_bindings.py:52`) — structurally not a choice, correct as-is.

All six committed bindings for the renta-income source set `fact` explicitly, so nothing is
wrong today: four in the M130 cumulative-income fragment, one each in the M100 2024 and 2025
income fragments. The exposure is prospective — a binding authored without an explicit `fact`
inherits the weakest measure silently.

**`gross_income_sum` is misnamed.** MEASURED against its own implementation: it sums the raw
bank amount. It is neither gross-of-retención nor IVA-exclusive. "Cash received" is what it
computes.

## Legal grounding for the income measure

REASONED on cited framework, with the verbatim-text boundary stated.

Modelo 130 casilla 01 is gross OF retención and exclusive of IVA repercutido.

- Gross of retención: RD 439/2007 art. 110.3.a, present in the bundled corpus, allows retenciones
  practicadas to be DEDUCTED from the computed pago. Retenciones therefore land in their own
  casilla, so income declared in casilla 01 must be pre-retención or the retención is counted
  twice.
- IVA-exclusive: LIRPF art. 27 defines rendimientos íntegros de actividades económicas and art.
  28.1 routes the net computation through Impuesto sobre Sociedades rules, reaching importe neto
  de la cifra de negocios, which excludes IVA repercutido as collected on behalf of Hacienda
  rather than revenue. **The accounting step of that chain — PGC norma de registro, Código de
  Comercio — is NOT in the bundled corpus.** That step is domain reasoning on the cited
  framework plus the AEAT Modelo 130 instructions, not bundled verbatim text. An ADR relying on
  it should confirm against live BOE.

Modelo 100's estimación-directa income leaf agrees with Modelo 130 by construction: the annual
aggregator reuses the same classifier and re-targets observations, so the measure is identical
and only the window differs. The cumulative year-to-date rule is Modelo 130 specific.

## Site 1 — ledger ingestion: what an invoice must declare

The operator's position, to be ruled on: a partial invoice declaration — issued or received,
lacking proper categorisation — is AMBIGUOUS and must be excluded from calculations, but must
NOT disappear. Advisories must ride on both the ledger surface and the calculation engine
stating that source data exists without calculation grounding.

Open questions for the ADR:

- What is the minimum declared shape for an invoice to be calculation-grounded? Base, IVA rate
  and amount, retención rate and amount, total, currency, operation territory, and counterparty
  tax residency are all candidates; which are required versus derivable.
- Where is the ambiguity boundary? A row with a base and no IVA may be legitimately exempt or
  merely untagged, and those are different states that currently look identical.
- Excluded-but-visible is a new outcome class. The income pipeline today has eligible and
  excluded-with-issue; a third state meaning "declarable but ungrounded" does not exist.
- The advisory channel already exists and is typed. Non-blocking diagnostics ride the notice
  channel on the CLI envelope, and the gasto and IVA pipelines already emit through it, so the
  income side is the outlier rather than the mechanism being absent.
- Severity is an operator decision: advisory permits filing on cash-derived income after a
  visible notice; blocking at verify prevents filing until substrate is recorded. A clean bank
  import with no invoice records is a plausible common state, and the error is only dangerous in
  the exempt-services case.

## Site 2 — calculation backend: decomposition by type and territory

The operator's position, to be ruled on: the engine must support the possible invoice types,
what their values represent, and how one invoice decomposes into base, IVA, retención and total
depending on type and operation territory — with currency normalisation, and with domestic,
intracomunitaria, and foreign/overseas categories changing WHICH components exist and how each
feeds the tax calculation.

Existing surfaces an ADR should build on rather than re-derive:

- The IVA category taxonomy already distinguishes domestic, intra-community supply and
  acquisition, reverse charge, import from third country, exempt, not-subject and OSS regimes,
  and the campaign confirmed a documented set of categories that are cuota-less by law.
- A currency normalisation service exists as a single path, and a predicate already refuses
  non-EUR rows lacking conversion.
- The M130 income and gasto halves now share one cumulative year-to-date window helper, so a
  decomposition change lands once for both halves.
- Seven ledger binding-value resolvers now share one generic, so a fact added to the dispatch
  contract reaches every family through one seam rather than seven.

Open questions for the ADR:

- Which components legitimately do not exist per category. An intra-community supply carries no
  repercutido cuota; an exempt professional service carries no IVA but may carry retención; a
  reverse-charge acquisition inverts who declares the cuota.
- Whether retención is ever derivable, or must always be declared. It is currently INFERRED as
  invoice gross minus cash, which only works when both are present.
- How territory interacts with the income measure. The M151 impatriado and M210 IRNR families
  already diverge here and both feed different modelos from the same ledger.
- Whether the fact taxonomy should be per-category rather than per-family, given that a
  category determines which components exist.

## Constraints any ruling must respect

- No silent under-declaration is a governing project rule. **Over-declaration harms the taxpayer
  and nothing currently watches that direction** — this campaign found the income default
  pointing at the over-declaring measure with no gate on it.
- Regulatory values live in the registry or central config, never inlined in feature modules.
- Every casilla observation must carry legal_refs and source_refs from registry source to
  operator-facing surface.
- Calculation tests may not assert numbers hand-computed from the formula under test; expected
  values come from AEAT workbooks, BOE examples, registry-authoritative fixtures, or live oracle
  replay.
- The application never files. Build, validate, verify and export only.

## Coverage state of the affected resolvers

MEASURED during the same sweep, relevant because an ADR here changes code that was until today
thinly pinned. Of seven ledger binding-value resolvers computing filed casilla values, one had no
behavioural coverage of any kind, one had a real committed binding that an existing test executed
without ever asserting its value, one was pinned only at the application layer, and one deliberate
asymmetry had no control that would fail if it were normalised away. Eighteen tests were added
closing those gaps. Three had genuinely adequate coverage as found.
