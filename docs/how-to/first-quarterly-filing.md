# Prepare your first quarterly IRPF filing

This page covers your first quarterly Modelo 130 filing, end to end: bring a
quarter of transactions into the ledger, classify them as business income and
deductible expenses, prepare the draft, and check that it passed verification
before you file it. It is written for a self-employed taxpayer with a NIF,
CIF, NIE, or other filing identity who is running Cadrumo for the first time.

Cadrumo never submits a return to the Agencia Estatal de Administración
Tributaria (AEAT). It produces the Modelo 130 fichero-BOE artefact locally;
you present that file through the official AEAT channel.

The commands on this page run live at build time in a fresh, synthetic sandbox.
The transactions, amounts, and taxpayer are invented. Run the same commands
against your own profile to see your own figures.

**Requirement:** a valid taxpayer profile. Create one with
`aeat config profile create <name>` before you start. [Set up your
profile](profile-setup.md) walks through it step by step.

## Bring your quarter's transactions in

Import your bank statement for the quarter. This example reads a small
comma-separated statement with two movements: one payment collected from a
client, and one office-supplies purchase.

```{cli-sequence} import-quarter-transactions
:verify: Confirm both movements are now in the ledger.
```

The import reads the statement and stores each movement as a ledger row. The
listing confirms the two rows landed in the first quarter of 2026. Point
`--provider` at the format your bank exports; list the accepted providers with:

```{cli-sequence} import-provider-list
:verify: Confirm the import command lists its accepted providers.
```

## Classify each transaction

An imported row carries a date and an amount, but it does not yet say how the
tax calculation should treat it. Classify each row before you calculate.

Mark the collected payment as business income and the purchase as a deductible
business expense with a category. Take each transaction id from the listing
above. The income classification takes only the business decision:

```{cli-sequence} first-quarter-classify-income
:verify: Confirm the collected payment is classified as business income.
```

For an expense, add `--category-id <category-id>` plus the taxable base and
IVA fields. List the accepted categories any time:

```{cli-sequence} ledger-category-list
:verify: Confirm the accepted expense categories read back.
```

For the full classification workflow (bulk classification, mixed-use shares,
and the review queue), read [Classify transactions](classify-transactions.md).

## Prepare the Modelo 130 draft

Once the quarter's rows are classified, prepare the instalment. The preparation
below sets up a self-employed profile and a classified ledger, then creates the
draft, calculates it, and verifies it. Modelo 130 is the IRPF payment on
account for self-employed activity under estimación directa.

```{cli-sequence} modelo-130-first-quarter
:verify: Confirm the draft passed verification before you file it.
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
  draft is complete and ready to file.

## Check the figures and record the filing

The verification result is the signal that the draft is ready. Verification
refuses until every deductible-expense row carries linked purchase-invoice
evidence, so this example registers the supplier invoice and attaches it before
it calculates. Attach in that order: a draft bundles its evidence when you
verify it, so an invoice attached afterwards does not reach the filing.

The sequence below exports the verified draft and then records the local filed
marker.

```{cli-sequence} first-quarter-export-file
:verify: Confirm the export succeeds and the filing marker stays local.
```

A later quarter builds on this one: leave the three prior-period bindings unset
so they resolve from your filed history. See
[Prepare a Modelo 130 IRPF instalment](modelo-130.md) for the cumulative
year-to-date behaviour.

## Next steps

- [Prepare a Modelo 130 IRPF instalment](modelo-130.md)
- [Classify transactions](classify-transactions.md)
- [The filing workflow](filing-spine.md)
- [File your modelo at the AEAT portal](file-at-aeat.md)
