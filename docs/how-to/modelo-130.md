# Prepare a Modelo 130 IRPF instalment

This page covers the quarterly Modelo 130 filing: the complete
create-calculate-verify-file chain, the cumulative year-to-date behaviour
that makes each quarter build on the ones before it, and the prior-period
values a later quarter carries in. Modelo 130 is the IRPF payment on account
for self-employed activity under estimación directa; the registry's official
title is "Impuesto sobre la Renta de las Personas Físicas. Actividades
económicas en estimación directa. Pago fraccionado."

`aeat` does not submit Modelo 130 to AEAT. It can produce the registry-backed
fichero-BOE upload file locally; you still present that file through the
official AEAT channel yourself.

The tool needs a master-key passphrase and prompts for it.

**Requirement:** a valid taxpayer profile with self-employed activity under
estimación directa. Create one with `aeat config profile create <name>` before
you start. [Set up your taxpayer profile](profile-setup.md) walks through it.

## The complete first-quarter chain

This is the full path from an empty store to a verified draft for a
first-period filer. The preparation below sets up a self-employed profile and a
classified ledger, then creates the draft, calculates it, and verifies it. Each
load-bearing detail is explained under the sequence.

```{cli-sequence} modelo-130-quarterly
:verify: Confirm the draft passed verification before you file it.
```

Load-bearing details:

- Create the profile with `--quiet` for the non-interactive form. The profile
  MUST carry `--name` and `--surnames`, or filing later refuses with
  "requires the operator name".
- `--activity-start-date 2026-01-01` scopes the prior-period dependency out
  for a first period. Without it, verify blocks on the previous quarter.
- `ledger add --amount` is the GROSS amount (`--taxable-base` +
  `--iva-amount`); the tool enforces the sum to the cent. A
  deductible-expense row needs `--category-id` (list ids with
  `aeat app ledger categories`).
- The three `--binding ...=0` values are the prior-period carries a true
  first period does not have: earlier quarters' negative results, earlier
  instalments paid, and last year's net income (used for the minoración).
  Later quarters resolve them from your own filed history instead - see
  [the cumulative behaviour](#each-quarter-is-cumulative) below.
- With the two rows above, calculate reports cumulative income (casilla `01`)
  of `1000.00`, rendimiento neto (casilla `03`) of `500.00` - income base
  minus expense base - and a pago fraccionado (casilla `04`) of `100.00`,
  20 percent of the net.
- `verify` reports `completeness complete` and `granted true`. `export` then
  writes the local fichero-BOE artefact and reports its checksum.

## Before you create the draft

- [Set up your taxpayer profile](profile-setup.md). Modelo 130 applies to a
  profile with self-employed activity under estimación directa; check
  applicability with `aeat app overview explain 130`.
- [Plan your filing calendar](filing-calendar.md). Modelo 130 uses quarterly
  periods `1T` through `4T` only.
- [Import or add your transactions](import-bank-statements.md), then
  [classify them](classify-transactions.md). Modelo 130 reads classified
  business income and expense rows; expenses need a category.

## What Modelo 130 calculates

Modelo 130 calculates the quarter's IRPF payment on account from your
activity's year-to-date figures: cumulative income (casilla `01`) minus
cumulative deductible expenses (casilla `02`) gives the rendimiento neto
(casilla `03`); the instalment (casilla `04`) is a percentage of that net;
prior instalments already paid this year (casilla `05`) and withholdings you
suffered (casilla `06`) come off; the minoración by net-income level
(casilla `13`) and negative results from earlier quarters (casilla `15`)
adjust the figure; and casilla `19` is the final result. A negative
casilla-17 balance is carried forward as
`saldo-negativo-fin-periodo` for later quarters.

The ledger feeds the cumulative income, expense, and withholding figures
through registry bindings; prior filings feed the carries. Casillas `06`,
`08`, `10`, `16`, and `18` are manual inputs for the cases that apply to you
(withholdings, second-activity volume, vivienda habitual deduction, prior
complementary results). Inspect what is bound, missing, or manual:

```{cli-sequence} modelo-130-inspect-boxes
:verify: Confirm the draft's bindings and the modelo's casilla definitions read back.
```

## Supply a manual box value

Casilla `06` (Retenciones e ingresos a cuenta) is a manual box: the ledger
does not fill it, so you supply it by hand with `--casilla`. Pass it in the
same calculate call as the first-period bindings, then review the saved
calculation to confirm your value landed:

```{cli-sequence} modelo-130-manual-casilla
:verify: Confirm the manual value you supplied appears in the saved calculation.
```

`--casilla` works only on `manual` boxes; a `bound` box filled from your ledger
(like casilla `02`) refuses the override. Check a box's kind with `aeat app
modelo casillas 130` (the inspect sequence above shows this), and see
[Review and supply calculation inputs](review-calculation-values.md) for the
full input workflow.

(each-quarter-is-cumulative)=
## Each quarter is cumulative

Modelo 130 is a year-to-date form, not a quarter-slice form. The second
quarter's casilla `01` covers January through June, not April through June;
each quarter's instalment is computed on the whole year so far, and the
instalments you already paid come off through casilla `05`.

The tool implements this through cumulative ledger bindings (the ledger
window for `2T` is January 1 to June 30) and `previous_filing` bindings that
read your own earlier filed quarters:

- `modelo-130-pagos-fraccionados-anteriores` - the instalments already paid
  this year, from your filed `1T`..`3T` records.
- `modelo-130-resultados-negativos-anteriores` - negative results carried
  from earlier quarters.
- `irpf.previous_year_economic_activity_net_income` - last year's net
  income, which decides the minoración tier.

For a first period these have no history, which is why the first-quarter
chain passes them as `--binding ...=0`. For later quarters do NOT pass
zeros: leave the bindings unset so they resolve from the filed prior
quarter. If the prior quarter is not filed and evidenced locally, verify
blocks with a cross-period finding - record or reconcile that earlier filing
first (see [Reconcile a filing](reconcile.md)).

## Calculate, review, verify, file

The chain is the standard filing workflow - see
[The filing workflow](filing-spine.md) for how work units and calculation
revisions behave. In short:

```{cli-sequence} modelo-130-review-chain
:verify: Confirm the draft calculates, reviews, and verifies before you file it.
```

Once the draft verifies, record the filed marker. Verification refuses until
every deductible-expense row carries linked purchase-invoice evidence (see
[Attach invoices and receipts](ledger-evidence.md)), so this example registers
the supplier invoice and attaches it before it calculates. Attach in that
order: a draft bundles its evidence when you verify it, so an invoice attached
afterwards does not reach the filing.

The sequence below exports the verified draft, then records the filed marker.

```{cli-sequence} modelo-130-export-file
:verify: Confirm the local export succeeds and the filing marker remains an internal record.
```

Recording the filed marker applies only while the obligation window is open. It
is an internal note that you have already presented the figures at the portal.

Each computed casilla carries its formula, legal references, and source
references; show them with the revision view or
[review the calculation values](review-calculation-values.md). If you recorded
the marker, reconcile against the justificante (see
[Reconcile a filing](reconcile.md)).

Modelo 130's quarterly results feed your annual Renta declaration: the four
instalments are folded into Modelo 100 as payments on account. See
[Prepare the annual Modelo 100 Renta declaration](modelo-100.md).

## Next steps

- [The income-tax year (run-through)](irpf-lifecycle.md)
- [The filing workflow](filing-spine.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [File your modelo at the AEAT portal](file-at-aeat.md)
- [Reconcile a filing](reconcile.md)
