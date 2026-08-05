---
tags:
  - '#research'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:e2961d8c683e650089be2be724aa17778232ded1d19c741a5c12dab27bcf93eb'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-adr]]"
  - "[[2026-08-05-ledger-invoice-decomposition-reference]]"
---

# `ledger-invoice-decomposition` research: `Calculation chain fragmentation across ledger, invoice, modelo and engine`

The question: does the ledger to invoice to calculation to declaration chain carry a
taxpayer's income to a filed casilla correctly, across every domain it crosses?

It does not, and the failure is structural rather than a defect list. The chain has no
single declared answer to what an invoice IS — which components exist, which are
derivable, which are legally required — so each domain answers locally and the answers
disagree. The disagreements are silent by construction: every layer answers correctly
about the fragment it was handed, and no layer owns the whole.

This document records the evidence picture. The decision is in the ADR of the same
feature stem, which this research feeds alongside the earlier reference document. Claims
below are marked MEASURED (read at the cited location at HEAD on 2026-08-05) or REASONED
(domain inference on a cited framework). Nothing here is quoted from the bundled corpus
without the distinction being stated.

## Findings

### The income measure is decided by a default, not by law

MEASURED. `_RentaLedgerIncomeSelector.fact` carries a default of `gross_income_sum`
(`src/cadrumo/domain/calculations/registry/_ledger_bindings.py:911`) while its sibling
`_ImpatriadoLedgerIncomeSelector.fact` defaults to `ingresos_integros_sum`
(`_ledger_impatriado_bindings.py:101`). One concept, two silent defaults, diverging on
the measure that determines a taxpayer's declared income.

`gross_income_sum` sums `abs(transaction.raw.amount)` — the bank-credited figure. It is
neither gross of retención nor exclusive of IVA. The name asserts a property the
implementation does not have, which is why the divergence survived review: a reader
checking the default reads a name that sounds correct.

Nothing is presently wrong: all committed bindings in both families declare `fact`
explicitly. The exposure is prospective and the direction matters — a binding authored
without an explicit `fact` silently inherits the weakest measure, and that measure
over-declares. The project's rule corpus guards the under-declaration direction
thoroughly and watches the over-declaration direction nowhere.

### No ingestion path populates the substrate the measure needs

MEASURED. No inbound financial adapter populates `taxable_base` — zero references under
`src/cadrumo/adapters/inbound/financial/`. The CSV, OFX, XLSX and N26-PDF providers set
raw fields only.

The `ingresos_integros_sum` fact falls back to `gross_amount` when `taxable_base_amount`
is `None` (`_ledger_bindings.py:1003-1012`). So a freelancer who imports bank statements,
tags rows with an actividad-económica category, and records no invoice has cash folded
into Modelo 130 casilla 01 and Modelo 100 casilla 0171.

**The resulting error changes direction with the invoice, which is why no single guard
catches it.** REASONED on the arithmetic: at 21% IVA with 15% retención the credited cash
is 1.06 times base, an over-declaration near 6%. For an IVA-exempt professional service
under LIVA article 20 with 15% retención, cash is 0.85 times base — a silent
under-declaration of 15% of base, on the central figure of the return.

It compounds within the same rows. MEASURED: `_income_withheld_amount`
(`src/cadrumo/application/aggregation/_renta_income_ledger.py:459-468`) requires BOTH
`taxable_base` and `iva_amount` to infer withholding, so rows lacking substrate
contribute zero to the retenciones casilla. Income is understated and the offsetting
credit is dropped, from one missing input.

### A second, opposite-direction silent zero in the same resolver

MEASURED. `taxable_base_sum` coerces a missing base to zero
(`_ledger_bindings.py:1013-1014`, `observation.taxable_base_amount or Decimal("0")`). Two
committed Modelo 130 casilla-01 bindings use this fact
(`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0003-m130-income-cumulative.toml:29`
and `:46`).

This always under-declares, where the fallback above can err either way. Two facts on one
resolver therefore fail in opposite directions, and a taxpayer's exposure depends on
which binding a registry author selected.

The Modelo 111 and 115 bindings also name `taxable_base_sum` but route through a
different selector class (`_retenciones_bindings.py:78` and `:125`), so they are a
separate surface despite the shared fact name — an example of the naming collisions that
make this chain hard to audit by symbol.

### The asymmetry that kept it invisible

MEASURED, and the sharpest structural finding. The gasto pipeline declares
`MISSING_TAXABLE_BASE` (`_renta_gasto_ledger.py:88`, raised at `:277`) and the IVA
pipeline carries the equivalent (`_iva_ledger.py:123`). Both surface the row rather than
folding it. The gasto docstring states the reason: IVA soportado is recovered through
Modelo 303 and is not a Renta gasto, so a declarable expense without a base is surfaced
instead of gross-folded.

The income pipeline's issue-reason enum has seven members and none covers missing
substrate. **The expense side deliberately refuses exactly the fold the income side
performs.** A shared enrollment gate already exists
(`src/cadrumo/application/aggregation/tests/test_shared_issue_reasons.py`) and the income
reason is absent from it — so the asymmetry is not merely undetected, it is unenrolled in
the mechanism built to detect it.

### No declared model of what components an invoice has

MEASURED as an absence. The IVA category taxonomy distinguishes domestic, intra-community
supply and acquisition, reverse charge, import from third country, exempt, not-subject
and OSS regimes, and `CUOTA_LESS_M303_IVA_CATEGORIES` (`src/cadrumo/domain/iva/_schema.py:163`)
records which bear no cuota by law. `EVIDENCE_EXEMPT_IVA_CATEGORIES` at `:184` is derived
from it rather than re-listed, which is the correct pattern and the precedent to extend.

What does not exist is the inverse statement: per category, which components an invoice
HAS. Cuota-less is recorded; base-only versus base-plus-cuota versus recipient-self-assessed,
and whether retención is expected, are not. Without that table each consumer infers
component existence from field nullness, and nullness cannot distinguish "legally absent"
from "not recorded". That single conflation is the root of the findings above: a base with
zero IVA and no category is indistinguishable from a declared-exempt supply.

### Where the substrate path is already correct

MEASURED, and worth stating because it bounds the work. When substrate IS recorded the
chain behaves: the Transaction gross invariant (`src/cadrumo/domain/transactions/_models.py:1118-1206`)
explicitly accepts net-paid incoming activity rows where cash is below base plus IVA, and
bounds inferred withholding by a registry maximum supported rate. A single FX normalisation
path exists with a predicate refusing unconverted non-EUR rows. Seven ledger binding-value
resolvers now share one generic (`_ledger_binding_resolution.py:38`), so a fact added to the
dispatch contract reaches every family through one seam. The Modelo 130 income and gasto
halves share one cumulative year-to-date window helper.

The gap is the ingestion contract and the component model, not the arithmetic.

### Coverage state of the affected resolvers

MEASURED during the same sweep, relevant because this work changes code that was until
recently thinly pinned. Of seven ledger binding-value resolvers computing filed casilla
values, one had no behavioural coverage of any kind, one had a committed binding an
existing test executed without ever asserting its value, one was pinned only at the
application layer, and one deliberate asymmetry had no control that would fail if it were
normalised away. Eighteen tests were added closing those gaps. Three had genuinely adequate
coverage as found — the finding is not that everything is untested.

### What was not investigated

Devengo versus cobros timing. The ledger is cash-dated while estimación directa defaults to
accrual unless the RD 439/2007 article 7.2 election is made. This is pre-existing, orthogonal
to the component model, and out of scope here — recorded so it is not mistaken for covered.

The accounting step establishing that IVA repercutido is excluded from the income measure
(PGC norma de registro y valoración, Código de Comercio) was not in the bundled corpus when
the reference document was written. The ADR records a live BOE cross-check closing that gap;
bundling the text is a named obligation of the implementation plan, and until it lands the
grounding is a cited framework rather than bundled verbatim text.

## Sources

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:911`, `:1003-1012`, `:1013-1014`
- `src/cadrumo/domain/calculations/registry/_ledger_impatriado_bindings.py:101`
- `src/cadrumo/domain/calculations/registry/_irnr_ledger_bindings.py:52`
- `src/cadrumo/domain/calculations/registry/_retenciones_bindings.py:78`, `:125`
- `src/cadrumo/domain/calculations/registry/_ledger_binding_resolution.py:38`
- `src/cadrumo/application/aggregation/_renta_income_ledger.py:434`, `:459-468`
- `src/cadrumo/application/aggregation/_renta_gasto_ledger.py:88`, `:277`
- `src/cadrumo/application/aggregation/_iva_ledger.py:123`
- `src/cadrumo/application/aggregation/tests/test_shared_issue_reasons.py`
- `src/cadrumo/domain/iva/_schema.py:163`, `:184`
- `src/cadrumo/domain/transactions/_models.py:1118-1206`
- `src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0003-m130-income-cumulative.toml:29`, `:46`
- `src/cadrumo/adapters/inbound/financial/` — absence of `taxable_base` population, verified by zero-hit search
- RD 439/2007 article 110.3.a — bundled corpus, read verbatim
- LIRPF articles 27 and 28.1 — bundled corpus
- LIVA article 20 — cited for the exempt-services case, corpus bundling pending
- PGC RD 1514/2007 NRV 12.ª and 14.ª — live BOE cross-check recorded in the ADR, not yet bundled
- RD 439/2007 article 95.1 — retención rates, live-verified, registry parameters pending
