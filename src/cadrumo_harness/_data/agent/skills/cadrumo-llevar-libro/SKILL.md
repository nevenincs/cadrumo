---
name: cadrumo-llevar-libro
description: >-
  Build and clean the ledger for a period: import bank statements, review the
  rows, correct them, split combined rows, merge duplicates and confirm the
  ledger check is clean. Use when statements or source records for a period need
  to enter the ledger, after onboarding and before classification.
applies_when:
  workflow_phase: ledger_upkeep
---

# Build the ledger

A correct ledger is the basis every calculation reads. Import faithfully, correct
the records, and confirm cleanliness. Never invent a transaction.

## Preconditions

- A profile is active (`aeat app overview status` reports one); if not, load
  `cadrumo-alta-contribuyente`.
- The statements and source records for the period are files in the conversation
  workspace. Ask the person for any that are missing; you cannot read files
  elsewhere.

## Procedure

1. Preview the import: `aeat app ledger import --file <PATH> --provider auto
   --dry-run` reads the file and reports what would be added without saving.
   `--provider` is required (`auto`, `csv`, `ofx`, `qfx`, `xlsx`, `xls` and
   `pdf-n26` are accepted), and `--period` with `--year` limits the import to one
   period. Read the result and any warnings, tell the person what will be
   imported, then run the same command without `--dry-run`. Tool server: operation
   `ledger.import`.
2. Review the result with `aeat app ledger list` (filter with `--period` and
   `--year`) and `aeat app ledger check`, which examines the rows and reports
   anomalies by period. Both only read.
3. Correct records where needed. Say what you will change before each change.
   - `aeat app ledger update <transaction-id>` replaces each field you give
     (operation `ledger.update`).
   - `aeat app ledger split <transaction-id> --child-amount ... --child-description ...`
     divides a combined row; the child amounts must add up exactly to the parent
     (operation `ledger.split.manual`).
   - `aeat app ledger merge --child-id ...` puts split children back together
     (operation `ledger.merge`). Name the rows to the person first and merge only
     after they agree in the conversation.
4. Run `aeat app ledger check` again until it reports nothing blocking. Pass the
   findings you cannot fix to the person.

## Success assertions

- Every imported row traces to a source record; no row is invented.
- `aeat app ledger check` reports no blocking findings.
- Statement and invoice content stays in the encrypted profile; none is copied to
  a scratch file.

## Next

A clean ledger is ready for `cadrumo-clasificar`.
