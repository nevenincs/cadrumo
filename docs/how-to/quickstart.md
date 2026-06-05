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

A profile is the taxpayer context that `aeat app` commands read and update. It
stores the taxpayer identity, activity, tax-regime facts, local ledger records,
and filing state for one taxpayer.

Create or check your profile before you import records or calculate a modelo:

```bash
aeat config profile create my-profile --quiet --tax-id 12345678Z
aeat config profile status
```

Profile setup asks specialized tax questions. Use
[Set up your taxpayer profile](profile-setup.md) to choose the right answers,
see every profile question group, work non-interactively with flags, list or
switch profiles, and export or import an existing profile.

## 2. Prepare transaction data

Transaction import is not automatic background sync. `aeat` imports only when
you run an import command or add a transaction yourself. Calculation later
consumes the saved, reviewed ledger for the active profile.

Start transaction work here:

```bash
aeat app ledger import ./statement.csv --provider auto --dry-run
aeat app ledger import ./statement.csv --provider auto
aeat app ledger list
```

Use [Work with transaction data](import-bank-statements.md) for the full
transaction workflow: import, add, update, remove, review, classify, allocate,
and run readiness checks.

## 3. Classify your transactions

Imported rows have no tax meaning until you classify them. Classification tells
`aeat` whether a row is business, personal, or mixed, and which category or tax
fields apply.

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

The command creates or reuses the local workspace for that filing. The deeper
workspace and revision model is explained in
[How filings, work units, and calculation revisions fit together](filing-spine.md).

## 6. Calculate and review values

Calculation combines four sources:

- the active taxpayer profile
- imported and classified transactions in that profile's ledger
- modelo registry rules, including formulas and casilla definitions
- explicit manual inputs or offsets where that modelo needs them

Run calculation for the same modelo, year, and period:

```bash
aeat app modelo work calculate --modelo 130 --year 2024 --period 1T
```

The command saves a new draft calculation revision. Review what was filled with:

```bash
aeat app modelo work revision --modelo 130 --year 2024 --period 1T
```

If a value is missing, if you need to provide a manual casilla value, or if an
offset/carry-forward value is involved, use
[Review and supply calculation inputs](review-calculation-values.md). That page
also explains how to inspect modelo casillas, descriptions, bindings,
calculation revisions, verification findings, and IVA compensation offsets.

## 7. Verify the draft

Verification checks that the current draft is complete enough for export. It is
a local check; it does not ask AEAT whether the filing will be accepted.

```bash
aeat app modelo work verify --modelo 130 --year 2024 --period 1T
```

When verification passes, `aeat` marks the selected draft as verified. If it
does not pass, fix the reported issue and calculate again before exporting.

## 8. Export the file

Export writes a fichero-BOE file, the fixed-width text file format AEAT accepts
for upload.

```bash
aeat app modelo export --modelo 130 --year 2024 --period 1T --output ./modelo-130-2024-1T.boe
```

The command prints the file path, size, and checksum. The checksum is a file
fingerprint you can use later when checking that the file has not changed.

## 9. File manually through AEAT

The final filing step is outside `aeat`:

1. Log in to the official AEAT electronic filing portal.
2. Choose the Modelo 130 file-upload path for the relevant year and period.
3. Upload the exported `.boe` file.
4. Review, sign, and keep the justificante AEAT issues after filing.

After a real filing, you can record the local filing marker:

```bash
aeat app modelo work file --modelo 130 --year 2024 --period 1T
```

This is local bookkeeping only. It records that you consider the verified draft
final, but it does not contact AEAT. To compare your local record with the AEAT
receipt, see [How to reconcile a filed modelo against its justificante](reconcile.md).

## Next steps

- [Set up your taxpayer profile](profile-setup.md) if profile facts are still
  incomplete.
- [Work with transaction data](import-bank-statements.md) when your ledger is
  not ready yet.
- [Classify transactions](classify-transactions.md) before calculating from
  imported rows.
- [Review and supply calculation inputs](review-calculation-values.md) when a
  modelo needs manual values, offsets, or binding review.
- [Diagnose and repair your local setup](troubleshooting.md) if a command stops
  or the local state looks wrong.
