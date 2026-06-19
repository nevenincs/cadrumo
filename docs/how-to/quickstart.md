# Quickstart: produce a modelo file

Use this when you are new to `aeat` and want the shortest path from local
records to a file you can upload yourself through the Agencia Estatal de
Administracion Tributaria (AEAT) portal.

`aeat` prepares, checks, and exports local files for Spanish tax forms. It does
not submit filings to AEAT. You remain responsible for reviewing and filing
through official AEAT channels.

This page follows one complete path: create a profile, add two transactions,
then calculate, verify, and export a Modelo 130 for the first quarter of 2026.
Every command below is run in order. It links to deeper guides whenever a step
has tax-specific setup or review choices.

## Before you start: the master-key passphrase

`aeat` encrypts your local data with a master key derived from a passphrase.
The first command that touches the store asks for the passphrase and the tool
reuses it for the rest of the session. To run without a prompt, set it in the
environment first:

```bash
export AEAT_SECRET_PASSPHRASE="your-passphrase"
```

The CLI emits its help and messages in Spanish. The English text on this page
describes what each step does.

## 1. Create your taxpayer profile

A profile is your personal taxpayer record inside the tool. Create it with your
own details. The name and surnames are required — the export step refuses
without them — and the activity start date scopes out prior periods so a first
filing has no earlier quarter to depend on:

```bash
aeat config profile create me --quiet --tax-id 12345678Z --name "Ana" \
  --surnames "Garcia Lopez" --activity "consultoria" \
  --activity-start-date 2026-01-01
aeat config profile status
```

`--quiet` runs without the interactive setup wizard. The create command
confirms the active profile and points you to the next step:

```text
profile	me
estado	creado
active_profile	me
next	aeat app modelo work create
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
from the recognised expense families:

```bash
aeat app ledger add --date 2026-02-10 --amount 1210 --direction INCOMING \
  --description "venta" --classification BUSINESS \
  --taxable-base 1000 --iva-rate 0.21 --iva-amount 210
aeat app ledger add --date 2026-02-11 --amount 605 --direction OUTGOING \
  --description "compra" --classification BUSINESS \
  --category-id material_oficina --taxable-base 500 --iva-rate 0.21 \
  --iva-amount 105
aeat app ledger list
```

List the recognised expense categories any time:

```bash
aeat app ledger categories
```

If you instead have a bank export, import it. `aeat` reads a semicolon-delimited
CSV with comma decimals and a negative `Importe` for money leaving the account:

```text
Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda
2026-02-10;2026-02-10;venta;1210,00;1210,00;EUR
2026-02-11;2026-02-11;compra;-605,00;605,00;EUR
```

Preview the import, then run it for real:

```bash
aeat app ledger import ./statement.csv --provider auto --dry-run
aeat app ledger import ./statement.csv --provider auto
```

Imported rows arrive without a tax category and must be classified before they
count in a calculation (see the next step). The `ledger add` rows above are
already classified, so you can skip straight to step 4.

Use [Work with Transactions](import-bank-statements.md) for the full
transaction workflow: import, add, update, remove, review, classify, allocate,
and run readiness checks.

## 3. Classify imported transactions

Each imported transaction has no tax category until you classify it.
Classification tells `aeat` whether a row is a business expense, personal
spending, or a mix of both. Take the transaction id from `ledger list`:

```bash
aeat app ledger classify <transaction-id> --classification BUSINESS \
  --category-id material_oficina
aeat app ledger preflight --year 2026 --period 1T
```

`preflight` reports whether the quarter's rows are ready to calculate.

Use [Classify transactions](classify-transactions.md) for the detailed review
path, including manual classification, bulk CSV classification, mixed-use
allocation, tax fields, and optional LLM suggestions.

## 4. Create a new draft

This creates a Modelo 130 draft for the first quarter of 2026. A modelo is a
Spanish tax form, and the year plus period identify the filing you are
preparing.

```bash
aeat app modelo work create --modelo 130 --year 2026 --period 1T
```

The command creates your filing workspace for that form if one does not exist
yet. Running it again returns the existing workspace.

`--period 1T` means the first quarter (primer trimestre). Other period codes
are `2T`, `3T`, `4T` for subsequent quarters and `0A` for an annual filing.

For more on how the tool organises your filing work behind the scenes, see
[How the tool organises your filing work](filing-spine.md).

## 5. Calculate the values

Run calculation for the same form, year, and period. Modelo 130 needs three
prior-period figures; for a first filing they are all zero. Pass them as
bindings so the calculation has no missing inputs:

```bash
aeat app modelo work calculate --modelo 130 --year 2026 --period 1T \
  --binding modelo-130-resultados-negativos-anteriores=0 \
  --binding modelo-130-pagos-fraccionados-anteriores=0 \
  --binding irpf.previous_year_economic_activity_net_income=0
```

The tool fills the boxes from your ledger and saves the result as a draft. The
summary shows the key figures, for example:

```text
role	casilla	value	label
key_figure	03	500.00	Rendimiento neto
key_figure	04	100.00	Importe del pago fraccionado
key_figure	19	0.00	Resultado final
```

Review every saved box with:

```bash
aeat app modelo work revision --modelo 130 --year 2026 --period 1T
```

If a value is missing or a modelo needs a value you must enter by hand, see
[Review and supply calculation inputs](review-calculation-values.md). That page
covers entering missing box values and handling figures carried forward from
earlier quarters.

## 6. Verify the draft

Verification checks that your draft is complete enough to export. It is a
local check — it does not send anything to AEAT or ask whether the filing will
be accepted.

```bash
aeat app modelo work verify --modelo 130 --year 2026 --period 1T
```

When the draft is complete, the report shows `completeness_status complete` and
`granted_verificado_completo true`, and `aeat` marks the draft as verified. A
first filing also shows one advisory noting that the period falls before your
activity start date; this is informational and does not block the export. If
verification reports a blocking issue, fix it and calculate again before
exporting.

## 7. Export the file

Export creates the `.boe` file — the format AEAT's upload portal accepts.

```bash
aeat app modelo export --modelo 130 --year 2026 --period 1T \
  --output ./modelo-130-2026-1T.boe
```

The tool shows where the file was saved, its size in bytes, and a `file_sha256`
verification code. Keep this code so you can later confirm you uploaded the
exact file that was generated.

## 8. Check what else is due (optional)

Use the local calendar to see what may be due for the active profile. On a fresh
profile, pass `--allow-incomplete` so the agenda runs before every profile fact
is filled in:

```bash
aeat app overview agenda --allow-incomplete
aeat app overview explain 130 --year 2026
```

The calendar uses profile facts and local filing context. It does not replace
AEAT's official portal. For the full calendar flow, see
[Plan your filing calendar](filing-calendar.md).

## 9. File manually through AEAT

The final filing step is outside `aeat`:

1. Log in to the official AEAT electronic filing portal.
2. Choose the Modelo 130 file-upload path for the relevant year and period.
3. Upload the exported `.boe` file.
4. Review, sign, and keep the justificante AEAT issues after filing.

The full handoff checklist, including what to do when the upload goes wrong,
is in [Upload your exported modelo at the AEAT portal](file-at-aeat.md).

After a real filing, you can record the local filing marker:

```bash
aeat app modelo work file --modelo 130 --year 2026 --period 1T
```

This only records the action on your own computer. It does not contact AEAT.
To compare your local record with the AEAT receipt, see
[How to reconcile a filed modelo against its justificante](reconcile.md).

## Next steps

- [Set up your taxpayer profile](profile-setup.md) if profile facts are still
  incomplete.
- [Work with Transactions](import-bank-statements.md) when your ledger is
  not ready yet.
- [Classify transactions](classify-transactions.md) before calculating from
  imported rows.
- [How your records become tax figures](../explanation/from-records-to-figures.md) - understand the transaction-to-box pipeline.
- [Review and supply calculation inputs](review-calculation-values.md) when a
  modelo needs manual values, offsets, or binding review.
- [Diagnose and repair your local setup](troubleshooting.md) if a command stops
  or the local state looks wrong.
