# Quickstart: produce a modelo file

Use this when you are new to `aeat` and want the shortest path from local
records to a file you can upload yourself through the Agencia Estatal de
Administracion Tributaria (AEAT) portal.

`aeat` prepares, checks, and exports local files for Spanish tax forms. It does
not submit filings to AEAT. You remain responsible for reviewing and filing
through official AEAT channels.

This page keeps the first path light. It links to deeper guides whenever a step
has tax-specific setup or review choices.

## 1. Create your taxpayer profile

A profile is your personal taxpayer record inside the tool. Create or check
your profile before you import records or calculate a modelo:

```bash
aeat config profile create my-profile --quiet --tax-id 12345678Z
aeat config profile status
```

Profile setup asks specialized tax questions. Use
[Set up your taxpayer profile](profile-setup.md) to choose the right answers,
see every profile question group, work non-interactively with flags, list or
switch profiles, and export or import an existing profile.

## 2. Prepare transaction data

Your bank records are not added automatically. Add them each time by running
an import command. The tax calculation later uses the income and expense records
you have imported and reviewed.

Start here:

```bash
aeat app ledger import ./statement.csv --provider auto --dry-run
aeat app ledger import ./statement.csv --provider auto
aeat app ledger list
```

Use [Work with Transactions](import-bank-statements.md) for the full
transaction workflow: import, add, update, remove, review, classify, allocate,
and run readiness checks.

## 3. Classify your transactions

Each imported transaction has no tax category until you classify it.
Classification tells `aeat` whether it is a business expense, personal
spending, or a mix of both.

```bash
aeat app ledger categories
aeat app ledger classify --id <transaction-id> --classification BUSINESS --category-id <category-id>
aeat app ledger preflight --period 2024Q1
```

Use [Classify transactions](classify-transactions.md) for the detailed review
path, including manual classification, bulk CSV classification, mixed-use
allocation, tax fields, and optional LLM suggestions.

## 4. Check your filing calendar

Use the local calendar to see what may be due for the active profile:

```bash
aeat app overview agenda
aeat app overview calendar --from 2024-01-01 --to 2024-12-31
aeat app overview explain 130 --year 2024
```

The calendar uses profile facts and local filing context. It does not replace
AEAT's official portal. For the full calendar flow, see
[Plan your filing calendar](filing-calendar.md).

## 5. Create a new draft

This example creates a Modelo 130 draft for the first quarter of 2024. A
modelo is a Spanish tax form, and the year plus period identify the filing you
are preparing.

```bash
aeat app modelo work create --modelo 130 --year 2024 --period 1T
```

The command creates your filing workspace for that form if one does not exist
yet. Running it again returns the existing workspace.

`--period 1T` means the first quarter (primer trimestre). Other period codes
are `2T`, `3T`, `4T` for subsequent quarters and `0A` for an annual filing.

For more on how the tool organises your filing work behind the scenes, see
[How the tool organises your filing work](filing-spine.md).

## 6. Calculate and review values

Run calculation for the same form, year, and period:

```bash
aeat app modelo work calculate --modelo 130 --year 2024 --period 1T
```

The tool saves the calculated values as a draft you can review before
exporting. See what was filled with:

```bash
aeat app modelo work revision --modelo 130 --year 2024 --period 1T
```

If a value is missing or a modelo needs a value you must enter by hand, see
[Review and supply calculation inputs](review-calculation-values.md). That page
covers entering missing box values and handling IVA credits carried forward from
earlier quarters.

## 7. Verify the draft

Verification checks that your draft is complete enough to export. It is a
local check — it does not send anything to AEAT or ask whether the filing will
be accepted.

```bash
aeat app modelo work verify --modelo 130 --year 2024 --period 1T
```

When verification passes, `aeat` marks the selected draft as verified. If it
does not pass, fix the reported issue and calculate again before exporting.

## 8. Export the file

Export creates the `.boe` file — the format AEAT's upload portal accepts.

```bash
aeat app modelo export --modelo 130 --year 2024 --period 1T --output ./modelo-130-2024-1T.boe
```

The tool shows where the file was saved, how large it is, and a verification
code. Keep this code so you can later confirm you uploaded the exact file that
was generated.

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
aeat app modelo work file --modelo 130 --year 2024 --period 1T
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
- [How calculations work](../explanation/ledger-to-calculation.md) - understand the transaction-to-box pipeline.
- [Review and supply calculation inputs](review-calculation-values.md) when a
  modelo needs manual values, offsets, or binding review.
- [Diagnose and repair your local setup](troubleshooting.md) if a command stops
  or the local state looks wrong.

