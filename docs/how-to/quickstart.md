# Quickstart: produce a modelo file

Use this when you are new to Cadrumo and want the shortest path from local
records to a file you can upload yourself through the Agencia Estatal de
Administración Tributaria (AEAT) portal.

Cadrumo, invoked as the `aeat` command, prepares, checks, and exports local
files for Spanish tax forms. It does not submit filings to AEAT. You remain responsible for reviewing and filing
through official AEAT channels.

This page follows one complete path: create a profile, add two transactions,
then calculate, verify, and export a Modelo 130 for the first quarter of 2026.
Every command below is run in order. It links to deeper guides whenever a step
has tax-specific setup or review choices.

**Requirement:** a valid taxpayer profile. Step 1 below creates one; if you
already have a profile, skip it. [Set up your taxpayer
profile](profile-setup.md) covers every profile question in depth.

## Before you start

This page assumes the `aeat` command is installed and on your path. Confirm
with:

```{cli-sequence} quickstart-version
:verify: Confirm the installed command reports its version.
@step Confirm the command is installed and on your path.
@result aeat --version
@expect exit_code == 0
```

If it is not, [Install Cadrumo](../workstation-setup.md) covers the full
setup: the package download, the optional integrations, and the AI-assistant
(MCP) surface.

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
@step Create your taxpayer profile with your own details.
@static aeat config profile create me --quiet --entity-type natural_person --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez" --activity "consultoria" --activity-start-date 2026-01-01
```

The name and surnames are required (the export step refuses without them), and
the activity start date scopes out prior periods so a first filing has no
earlier quarter to depend on. `--quiet` runs without the interactive setup
wizard.

Confirm the active profile is configured and ready:

```{cli-sequence} quickstart-profile
:verify: Confirm the active profile is configured and ready.
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01
@step Read the active profile status.
@result aeat --format json config profile status
@expect result.configured == true
@expect exit_code == 0
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
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01
@step Add the income row directly with its tax fields.
aeat --format json app ledger add --date 2026-02-10 --amount 1210 --direction INCOMING --description "venta" --classification BUSINESS --taxable-base 1000 --iva-rate 0.21 --iva-amount 210 --idempotency-key qs-venta
@step Add the deductible expense row with its expense category.
aeat --format json app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING --description "compra" --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105 --idempotency-key qs-compra
@step List the ledger to confirm both rows.
@result aeat --format json app ledger list
@expect exit_code == 0
```

List the recognised expense categories any time:

```{cli-sequence} quickstart-categories
:verify: Confirm the expense category catalogue lists.
@step List the recognised expense categories.
@result aeat --format json app ledger categories
@expect exit_code == 0
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
@static aeat app ledger import ./statement.csv --provider auto --dry-run
@static aeat app ledger import ./statement.csv --provider auto
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
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01
@step Add the expense row, then take its id from the output.
aeat --format json app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING --description "compra" --classification BUSINESS --category-id material_oficina --taxable-base 500 --iva-rate 0.21 --iva-amount 105 --idempotency-key qs-compra
@capture transaction_id result.transaction_id
@step Classify the transaction as a business expense.
aeat --format json app ledger classify {transaction_id} --classification BUSINESS --category-id material_oficina
@step Check the quarter's rows are ready to calculate.
@result aeat --format json app ledger preflight --year 2026 --period 1T
@expect exit_code == 0
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
:seed: quickstart-ledger
:verify: Confirm the draft passed verification before you export it.
@step Create a Modelo 130 draft for the first quarter of 2026.
aeat --format json app modelo work create --modelo 130 --year 2026 --period 1T
@capture work_unit_id result.work_unit_id
@step Calculate the draft from the classified ledger.
aeat --format json app modelo work calculate {work_unit_id} --binding modelo-130-resultados-negativos-anteriores=0 --binding modelo-130-pagos-fraccionados-anteriores=0 --binding irpf.previous_year_economic_activity_net_income=0
@capture calculation_revision_id result.calculation_revision_id
@expect result.casilla_values.01 == "1000"
@expect result.casilla_values.03 == "500.00"
@expect result.casilla_values.04 == "100.00"
@step Verify the draft before exporting.
@result aeat --format json app modelo work verify {calculation_revision_id}
@expect result.granted_verificado_completo == true
@expect exit_code == 0
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
  informational and does not block the export.

Review every saved box with:

```{cli-sequence} quickstart-revision
:seed: quickstart-ledger
:verify: Confirm the saved revision shows the calculated boxes.
@setup aeat app modelo work create --modelo 130 --year 2026 --period 1T
@setup aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --binding modelo-130-resultados-negativos-anteriores=0 --binding modelo-130-pagos-fraccionados-anteriores=0 --binding irpf.previous_year_economic_activity_net_income=0
@step Show every saved box for the filing.
@result aeat --format json app modelo work revision --modelo 130 --year 2026 --period 1T
@expect exit_code == 0
```

If a value is missing or a modelo needs a value you must enter by hand, see
[Review and supply calculation inputs](review-calculation-values.md). That page
covers entering missing box values and handling figures carried forward from
earlier quarters. For how the tool organises filing work behind the scenes, see
[The filing workflow](filing-spine.md).

## 5. Export the file

Export creates the `.boe` file, the format AEAT's upload portal accepts:

```{cli-sequence} quickstart-export
@static aeat app modelo export --modelo 130 --year 2026 --period 1T --output ./modelo-130-2026-1T.boe
```

The tool shows where the file was saved, its size in bytes, and a `file_sha256`
verification code. Keep this code so you can later confirm you uploaded the
exact file that was generated.

This example uses a deductible-IVA expense, and export refuses that until the
purchase invoice is linked as evidence (the message reads `Deductible IVA
ledger rows require linked purchase invoice evidence`). Attach the invoice
first, then re-run the export. [Attach invoices and receipts](ledger-evidence.md)
and [Prepare a Modelo 303 IVA filing](modelo-303.md) walk through the evidence
workflow end to end.

## 6. Check what else is due (optional)

Use the local calendar to see what may be due for the active profile. On a fresh
profile, pass `--allow-incomplete` so the agenda runs before every profile fact
is filled in:

```{cli-sequence} quickstart-agenda
:verify: Confirm the agenda and the Modelo 130 explanation read back.
@setup aeat config profile edit docs-sequence-sandbox --quiet --accept-defaults --activity-start-date 2026-01-01
@step Show what may be due for the active profile.
aeat --format json app overview agenda --allow-incomplete
@step Explain why Modelo 130 applies this year.
@result aeat --format json app overview explain 130 --year 2026
@expect exit_code == 0
```

The calendar uses profile facts and local filing context. It does not replace
AEAT's official portal. For the full calendar flow, see
[Plan your filing calendar](filing-calendar.md).

## 7. File manually through AEAT

The final filing step is outside `aeat`:

1. Log in to the official AEAT electronic filing portal.
2. Choose the Modelo 130 file-upload path for the relevant year and period.
3. Upload the exported `.boe` file.
4. Review, sign, and keep the justificante AEAT issues after filing.

The full handoff checklist, including what to do when the upload goes wrong,
is in [Upload your exported modelo at the AEAT portal](file-at-aeat.md).

After a real filing, record the local filing marker:

```{cli-sequence} quickstart-file
@static aeat app modelo work file --modelo 130 --year 2026 --period 1T
```

Like export, `work file` needs the deductible-IVA expense's invoice linked as
evidence first (it refuses with `Deductible IVA ledger rows require linked
purchase invoice evidence`). Attach the invoice, then record the marker.

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
