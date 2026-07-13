# Prepare a Modelo 130 IRPF instalment

This page covers the quarterly Modelo 130 filing: the complete
create-calculate-verify-export chain, the cumulative year-to-date behaviour
that makes each quarter build on the ones before it, and the prior-period
values a later quarter carries in. Modelo 130 is the IRPF payment on account
for self-employed activity under estimación directa; the registry's official
title is "Impuesto sobre la Renta de las Personas Físicas. Actividades
económicas en estimación directa. Pago fraccionado."

`aeat` does not submit Modelo 130 to AEAT. Export creates a local file that
you upload through the official AEAT channel yourself.

The tool needs a master-key passphrase and prompts for it.

## The complete first-quarter chain

This is the full path from an empty store to an exported `.boe` for a
first-period filer. Run these commands in order. Each load-bearing detail is
explained below.

```bash
aeat config profile create me --quiet --tax-id 12345678Z --name "Ana" \
  --surnames "Garcia Lopez" --activity "consultoria" --activity-start-date 2026-01-01
aeat app ledger add --date 2026-02-10 --amount 1210 --direction INCOMING \
  --description "venta" --classification BUSINESS \
  --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
aeat app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING \
  --description "compra" --classification BUSINESS --category-id material_oficina \
  --taxable-base 500 --iva-rate 0.21 --iva-amount 105
aeat app modelo work create --modelo 130 --year 2026 --period 1T
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T \
  --binding modelo-130-resultados-negativos-anteriores=0 \
  --binding modelo-130-pagos-fraccionados-anteriores=0 \
  --binding irpf.previous_year_economic_activity_net_income=0
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
aeat app modelo export --modelo 130 --year 2026 --period 1T --output ./modelo-130.boe
```

Load-bearing details:

- Create the profile with `--quiet` for the non-interactive form. The profile
  MUST carry `--name` and `--surnames`, or export later refuses with
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
- With the two rows above, calculate reports rendimiento neto (casilla `03`)
  of `500.00` - income base minus expense base - and a pago fraccionado
  (casilla `04`) of `100.00`, 20 percent of the net.
- `verify` reports `completeness complete` and `granted true`. `export`
  writes the `.boe` and reports its path, byte size, and SHA-256 checksum.

## Before you create the draft

- [Set up your taxpayer profile](profile-setup.md). Modelo 130 applies to a
  profile with self-employed activity under estimación directa; check
  applicability with `aeat app overview explain 130 --year 2026`.
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

```bash
aeat app modelo bindings list --modelo 130 --year 2026 --period 1T
aeat app modelo casillas 130 --period 1T
```

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

## Calculate, review, verify, export

The chain is the standard filing workflow - see
[The filing workflow](filing-spine.md) for how work units and calculation
revisions behave. In short:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T
aeat app modelo work revision --modelo 130 --year 2026 --period 1T
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
aeat app modelo export --modelo 130 --year 2026 --period 1T --output ./modelo-130.boe
```

Each computed casilla carries its formula, legal references, and source
references; show them with the revision view or
[review the calculation values](review-calculation-values.md). After you
upload the exported file at the portal, record the local marker with
`aeat app modelo work file --modelo 130 --year 2026 --period 1T` and
reconcile against the justificante.

Modelo 130's quarterly results feed your annual Renta declaration: the four
instalments are folded into Modelo 100 as payments on account. See
[Prepare the annual Modelo 100 Renta declaration](modelo-100.md).

## Next steps

- [The income-tax year (run-through)](irpf-lifecycle.md)
- [The filing workflow](filing-spine.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [Upload your exported modelo at the AEAT portal](file-at-aeat.md)
- [Reconcile a filing](reconcile.md)
