# Quickstart: prepare a modelo filing

Use this when you are new to Cadrumo and want the shortest path from local
records to figures you can present yourself at the Agencia Estatal de
Administración Tributaria (AEAT) portal.

Cadrumo, invoked as the `aeat` command, prepares and checks local records for
Spanish tax forms. It does not submit filings to AEAT. You remain responsible
for reviewing and filing through official AEAT channels.

This page follows one complete path: create a profile, add two transactions,
then calculate, verify, and file a Modelo 130 for the first quarter of 2026.
Every command below is run in order. It links to deeper guides whenever a step
has tax-specific setup or review choices.

**Requirement:** a valid taxpayer profile. Step 1 below creates one; if you
already have a profile, skip it. [Set up your taxpayer
profile](profile-setup.md) covers every profile question in depth.

## Before you start

This page assumes the `aeat` command is installed and on your path. Confirm
with:

```{cli-sequence} quickstart-version
:verify: Confirm the command is installed and the active profile is ready.
```

If it is not, [Install Cadrumo](../workstation-setup.md) covers the full
setup, including the package download and optional integrations.

## The master-key passphrase

`aeat` encrypts your local data with a master key derived from a passphrase.
The first command that touches the store asks for the passphrase and the tool
reuses it for the rest of the session. For unattended runs, see
[Run without a passphrase prompt](protect-data-access.md#run-without-a-passphrase-prompt).

The CLI emits its help and messages in Spanish. The English text on this page
describes what each step does.

## 1. Create your taxpayer profile

A profile is your personal taxpayer record inside the tool. Create it with your
own details:

```{cli-sequence} quickstart-create-profile
:verify: Confirm the profile is created and becomes the active profile.
```

The name and surnames are required (filing refuses without them), and
the activity start date scopes out prior periods so a first filing has no
earlier quarter to depend on. `--quiet` runs without the interactive setup
wizard.

Confirm the active profile is configured and ready:

```{cli-sequence} quickstart-profile
:verify: Confirm the active profile is configured and ready.
```

Profile setup can ask many more tax questions. Use
[Set up your taxpayer profile](profile-setup.md) to choose the right answers,
see every profile question group, list or switch profiles, and export or import
an existing profile.

## 2. Add your transactions

The tax calculation uses the income and expense records in your ledger. There
are two ways to add them.

The simplest is to add each row directly with its tax fields. `--amount` is the
gross total (taxable base plus IVA); an expense row also needs a `--category-id`
from the recognised expense families. The `--idempotency-key` on each row makes
it safe to re-run without adding a duplicate:

```{cli-sequence} quickstart-transactions
:verify: Confirm both classified rows land in the ledger.
```

List the recognised expense categories any time:

```{cli-sequence} quickstart-categories
:verify: Confirm the expense category catalogue lists.
```

If you instead have a bank export, import it. `aeat` reads a semicolon-delimited
CSV with comma decimals and a negative `Importe` for money leaving the account:

```text
Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda
2026-02-10;2026-02-10;venta;1210,00;1210,00;EUR
2026-02-11;2026-02-11;compra;-605,00;605,00;EUR
```

Preview the import, then run it for real (shown as a display-only example,
since running it here would duplicate the two rows added above):

```{cli-sequence} quickstart-import
```

Imported rows arrive without a tax category and must be classified before they
count in a calculation (see the next step). The `ledger add` rows above are
already classified, so you can skip straight to step 4.

Use [Import and manage transactions](import-bank-statements.md) for the full
transaction workflow: import, add, update, remove, review, classify, allocate,
and run readiness checks.

## 3. Classify imported transactions

Each imported transaction has no tax category until you classify it.
Classification tells `aeat` whether a row is a business expense, personal
spending, or a mix of both. Take the transaction id from the row's output, then
classify it and check the quarter is ready:

```{cli-sequence} quickstart-classify
:verify: Confirm the classified quarter passes the ledger preflight.
```

`preflight` reports whether the quarter's rows are ready to calculate.

Use [Classify transactions](classify-transactions.md) for the detailed review
path, including manual classification, bulk CSV classification, mixed-use
allocation, tax fields, and optional LLM suggestions.

## 4. Create, calculate, and verify the draft

With the profile and a classified ledger in place, prepare the Modelo 130 draft
for the first quarter of 2026, calculate it, and verify it. A modelo is a
Spanish tax form, and the year plus period identify the filing you are
preparing.

```{cli-sequence} quickstart-modelo-130
:verify: Confirm the draft passed verification before you file it.
```

Read the frames in order:

- Create the draft. The command creates your filing workspace for that form if
  one does not exist yet; running it again returns the existing workspace.
  `--period 1T` means the first quarter (primer trimestre). Other period codes
  are `2T`, `3T`, `4T` for subsequent quarters and `0A` for an annual filing.
- Calculate the values. Modelo 130 needs three prior-period figures; for a first
  filing they are all zero, passed as bindings so the calculation has no missing
  inputs. The tool fills the boxes from your ledger: casilla `01` is the
  quarter's income (`1000.00`, the taxable base, since IVA is never part of your
  income), casilla `03` the net yield (`500.00`), and casilla `04` the
  instalment (`100.00`, twenty percent of the net).
- Verify the draft. Verification is a local check. It does not send anything to
  AEAT. When the draft is complete the report reads `completeness_status
  complete` and `granted_verificado_completo true`. A first filing also shows one
  advisory noting that the period falls before your activity start date; this is
  informational and does not block filing.

Review every saved box with:

```{cli-sequence} quickstart-revision
:verify: Confirm the saved revision shows the calculated boxes.
```

If a value is missing or a modelo needs a value you must enter by hand, see
[Review and supply calculation inputs](review-calculation-values.md). That page
covers entering missing box values and handling figures carried forward from
earlier quarters. For how the tool organises filing work behind the scenes, see
[The filing workflow](filing-spine.md).

## 5. Record the quarter as filed

Modelo 130 has no fichero-BOE layout, so export refuses. Record the quarter as
filed locally instead:

```{cli-sequence} quickstart-export
:verify: Confirm the export refuses and the local filing marker is recorded.
```

The refusal is deliberate. A fichero-BOE layout is published only once every
field it contains can be produced from checked values, because a partial layout
can under-declare without saying so. Calculation, verification and the local
filing record all still work; only the upload file is unavailable.

Enter the calculated box values yourself at the AEAT portal, as step 7
describes.

This example uses a deductible-IVA expense, so it links the purchase invoice
before calculating. Verification refuses a deducted IVA row that carries no
invoice (the message reads `Deductible IVA ledger rows require linked purchase
invoice evidence`).

Link the invoice while you record the expense, before you calculate. A draft
bundles its evidence when you verify it, so an invoice attached afterwards does
not reach a draft that is already verified. [Attach invoices and
receipts](ledger-evidence.md) and [Prepare a Modelo 303 IVA
filing](modelo-303.md) walk through the evidence workflow end to end.

## 6. Check what else is due (optional)

Use the local calendar to see what may be due for the active profile. On a fresh
profile, pass `--allow-incomplete` so the agenda runs before every profile fact
is filled in:

```{cli-sequence} quickstart-agenda
:verify: Confirm the agenda and the Modelo 130 explanation read back.
```

The calendar uses profile facts and local filing context. It does not replace
AEAT's official portal. For the full calendar flow, see
[Plan your filing calendar](filing-calendar.md).

## 7. File manually through AEAT

The final filing step is outside `aeat`:

1. Log in to the official AEAT electronic filing portal.
2. Open the Modelo 130 form for the relevant year and period.
3. Enter the box values the calculation produced. The command card below reads
   them back before it records the local filing marker.
4. Review, sign, and keep the justificante AEAT issues after filing.

The full handoff checklist is in
[File your modelo at the AEAT portal](file-at-aeat.md).

After a real filing, record the local filing marker:

```{cli-sequence} quickstart-file
:verify: Confirm the local filed marker recorded.
```

`work file` refuses a deducted IVA row whose invoice is not linked
(`Deductible IVA ledger rows require linked purchase invoice evidence`). The
draft verified above already carries its invoice, so the marker records.

This only records the action on your own computer. It does not contact AEAT.
To compare your local record with the AEAT receipt, see
[How to reconcile a filed modelo against its justificante](reconcile.md).

## Next steps

- [Set up your taxpayer profile](profile-setup.md) if profile facts are still
  incomplete.
- [Import and manage transactions](import-bank-statements.md) when your ledger is
  not ready yet.
- [Classify transactions](classify-transactions.md) before calculating from
  imported rows.
- [How your records become tax figures](../explanation/from-records-to-figures.md) - understand the transaction-to-box pipeline.
- [Review and supply calculation inputs](review-calculation-values.md) when a
  modelo needs manual values, offsets, or binding review.
- [Diagnose and repair your local setup](troubleshooting.md) if a command stops
  or the local state looks wrong.
