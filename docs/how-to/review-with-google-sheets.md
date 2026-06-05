# Review calculations with Google Sheets

Use this guide when you want to review a modelo calculation surface in Google
Sheets. This workflow is for calculation review and verification after your
profile and transactions are ready. It is not a ledger import or ledger batch
edit workflow.

The Google commands use the active profile. They manage Google OAuth, a Drive
folder binding, and calc-sheets workbooks for a modelo, year, and period.

## Before you start

You need:

- an active profile; see [Set up your taxpayer profile](profile-setup.md)
- classified transaction data; see [Work with Transactions](import-bank-statements.md)
- a modelo and period ready enough to calculate
- a Google Desktop OAuth client JSON file
- a Google Drive folder id that you want `aeat` to use

## Configure Google access

Register the Desktop OAuth client for the active profile:

```bash
aeat config google register --client-json ./client_secret.json
```

Run the Google consent flow:

```bash
aeat config google login
aeat config google status
```

Bind a Drive folder:

```bash
aeat config google folder set <drive-folder-id>
aeat config google folder get
aeat config google sync probe
```

The Google integration is profile-scoped. If you switch profiles, check Google
status and folder binding again.

## Export a calculation workbook

Export the registry calculation surface for one modelo, year, and period:

```bash
aeat config google sync calc export --modelo 303 --year 2026 --period 1T
```

The export creates a Google Sheets workbook inside the configured `aeat-vault/`
area in Drive. It is a calculation review surface, not a bank statement export.
Use `aeat app ledger export` when you need a CSV, JSONL, or XLSX snapshot of
ledger rows.

Use `--prefill-relations` only when you intentionally want the export to
prefill relation values from local observations such as annual summaries or
prior-quarter carryovers.

## Pull operator edits

After reviewing or editing the workbook, pull typed edits back from the Sheet:

```bash
aeat config google sync calc pull --modelo 303 --year 2026 --period 1T --spreadsheet-id <spreadsheet-id>
```

Add `--compute` when you want the local Decimal engine to compute casilla
values from the pulled edits:

```bash
aeat config google sync calc pull --modelo 303 --year 2026 --period 1T --spreadsheet-id <spreadsheet-id> --compute
```

Add `--assemble-observations` when you want row-set detail edits assembled into
typed observations in the pull payload.

The pull command validates that the workbook belongs to the app surface and
matches the registry snapshot. If it refuses, re-export for the active profile
and retry from the new workbook.

## Verify the calculation surface

Run the calc-sheets verification command for the same modelo, year, and period:

```bash
aeat config google sync calc verify --modelo 303 --year 2026 --period 1T
```

If you have a scenario JSON with operator inputs and expected AEAT outputs,
pass it explicitly:

```bash
aeat config google sync calc verify --modelo 303 --year 2026 --period 1T --scenario ./scenario.json
```

Verification compares the calculation surfaces implemented by the app. It does
not submit a filing to AEAT.

## Where this fits

Use this after transaction review and classification:

```bash
aeat app ledger preflight --period 2026Q1
aeat app ledger status --period 2026Q1
```

If the ledger still has missing categories, IVA fields, currency, or
proportionality references, finish those in
[Classify transactions](classify-transactions.md) before relying on the
calculation workbook.

For casilla-level manual inputs, bindings, offsets, and revisions, use
[Review and supply calculation inputs](review-calculation-values.md).

## Next steps

- [Work with Transactions](import-bank-statements.md)
- [Classify transactions](classify-transactions.md)
- [Review and supply calculation inputs](review-calculation-values.md)
- [CLI reference](../cli/index.rst)
