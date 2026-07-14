# Prepare your first quarterly IRPF filing

This page covers your first quarterly Modelo 130 filing, end to end: bring a
quarter of transactions into the ledger, classify them as business income and
deductible expenses, prepare the draft, and check that it passed verification
before you export it. It is written for a self-employed taxpayer with a NIF,
CIF, NIE, or other filing identity who is running Cadrumo for the first time.

Cadrumo never submits a return to the Agencia Estatal de Administración
Tributaria (AEAT). Every command below builds and checks a local file. You
upload the exported file yourself through the official AEAT channel.

The commands on this page run live at build time in a fresh, synthetic sandbox.
The transactions, amounts, and taxpayer are invented. Run the same commands
against your own profile to see your own figures.

**Requirement:** a valid taxpayer profile. Create one with
`aeat config profile create <name>` before you start — [Set up your
profile](profile-setup.md) walks through it step by step.

## Bring your quarter's transactions in

Import your bank statement for the quarter. This example reads a small
comma-separated statement with two movements: one payment collected from a
client, and one office-supplies purchase.

```{cli-sequence} import-quarter-transactions
:verify: Confirm both movements are now in the ledger.
@step Bring the quarter's bank movements into the ledger.
aeat app ledger import fixtures/movimientos-2026-1t.csv --provider csv
@step Check that the quarter's ledger now holds both movements.
@result aeat --format json app ledger list --year 2026 --period 1T
@expect result.total == 2
@expect exit_code == 0
```

The import reads the statement and stores each movement as a ledger row. The
listing confirms the two rows landed in the first quarter of 2026. Point
`--provider` at the format your bank exports; list the accepted providers with:

```{cli-sequence} import-provider-list
:verify: Confirm the import command lists its accepted providers.
@step Show the import command's help, including the accepted providers.
@result aeat app ledger import --help
@expect exit_code == 0
```

## Classify each transaction

An imported row carries a date and an amount, but it does not yet say how the
tax calculation should treat it. Classify each row before you calculate.

Mark the collected payment as business income and the purchase as a deductible
business expense with a category. Take each transaction id from the listing
above. For income, run `aeat app ledger classify <transaction-id>
--classification BUSINESS`.

For an expense, add `--category-id <category-id>` plus the taxable base and
IVA fields. List the accepted categories any time:

```{cli-sequence} ledger-category-list
:verify: Confirm the accepted expense categories read back.
@step List the accepted expense categories.
@result aeat --format json app ledger categories
@expect exit_code == 0
```

For the full classification workflow — bulk classification, mixed-use shares,
and the review queue — read [Classify transactions](classify-transactions.md).

## Prepare the Modelo 130 draft

Once the quarter's rows are classified, prepare the instalment. The preparation
below sets up a self-employed profile and a classified ledger, then creates the
draft, calculates it, and verifies it. Modelo 130 is the IRPF payment on
account for self-employed activity under estimación directa.

```{cli-sequence} modelo-130-first-quarter
:seed: autonomo-irpf-2026
:verify: Confirm the draft passed verification before you export it.
@step Open a Modelo 130 draft for the first quarter.
aeat --format json app modelo work create --modelo 130 --year 2026 --period 1T
@capture work_unit_id result.work_unit_id
@step Calculate the quarter's instalment from the classified ledger.
aeat --format json app modelo work calculate {work_unit_id} --binding modelo-130-resultados-negativos-anteriores=0 --binding modelo-130-pagos-fraccionados-anteriores=0 --binding irpf.previous_year_economic_activity_net_income=0
@capture calculation_revision_id result.calculation_revision_id
@expect result.casilla_values.01 == "1000"
@expect result.casilla_values.03 == "500.00"
@expect result.casilla_values.04 == "100.00"
@step Verify the draft before you export it.
@result aeat --format json app modelo work verify {calculation_revision_id}
@expect result.granted_verificado_completo == true
@expect exit_code == 0
```

Read the frames in order:

- Create the draft for Modelo 130, first quarter 2026. The command reports a
  `work_unit_id` that addresses the draft.
- Calculate it. Cadrumo reads the classified ledger and fills the boxes:
  casilla `01` is the quarter's income, casilla `02` the deductible expenses,
  casilla `03` the net yield, and casilla `04` the instalment. Casilla 01 shows
  1000.00, not the 1210.00 you collected: IVA is never part of your income, so
  the 210.00 of IVA is left out. With the example ledger the net yield is
  `500.00` and the instalment is `100.00`, twenty percent of the net. The three
  `--binding ...=0` values are the prior-period carries a true first quarter
  does not have.
- Verify the draft. The result reads `granted_verificado_completo` true, so the
  draft is complete and ready to export.

## Check the figures and export

The verification result is the signal that the draft is ready. When
`granted_verificado_completo` reads true, export the file with `aeat app modelo
export --modelo 130 --year 2026 --period 1T --output ./modelo-130.boe`. Export
refuses until every deductible-expense row carries linked purchase-invoice
evidence — the full evidence-to-export chain runs end to end on
[Prepare a Modelo 303 IVA filing](modelo-303.md).

Upload it at the AEAT portal yourself, then record the local marker with `aeat
app modelo work file --modelo 130 --year 2026 --period 1T`.

A later quarter builds on this one: leave the three prior-period bindings unset
so they resolve from your filed history. See
[Prepare a Modelo 130 IRPF instalment](modelo-130.md) for the cumulative
year-to-date behaviour.

## Next steps

- [Prepare a Modelo 130 IRPF instalment](modelo-130.md)
- [Classify transactions](classify-transactions.md)
- [The filing workflow](filing-spine.md)
- [Upload your exported modelo at the AEAT portal](file-at-aeat.md)
