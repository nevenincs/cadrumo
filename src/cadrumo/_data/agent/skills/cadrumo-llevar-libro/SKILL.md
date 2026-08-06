---
name: cadrumo-llevar-libro
description: >-
  Build and clean the ledger for a period: import bank statements, review, correct,
  split combined rows, merge duplicates, and confirm the ledger is clean. Use after
  onboarding and before classification.
applies_when:
  workflow_phase: ledger_upkeep
---

# Build the ledger

A correct ledger is the basis every calculation reads. Import faithfully, correct
the records, and confirm cleanliness. Never invent a transaction.

## Preconditions

- An active profile exists (`aeat app overview status` reports one).
- You hold the period's bank statements and source records.

## Procedure

1. Import a statement: `aeat app ledger import --file STATEMENT.csv`. Read the
   envelope and any `warning` notices.
2. Review the result: `aeat app ledger list` and `aeat app ledger check`.
3. Correct records where needed: `aeat app ledger update` for a field fix,
   `aeat app ledger split` for a combined row, `aeat app ledger merge` for
   duplicates.
4. Re-run `aeat app ledger check` until it is clean.

## Success assertions

- Every imported row traces to a source record; no row is invented.
- `aeat app ledger check` reports a clean ledger (no blocking findings).
- Statement and invoice bytes are stored only in the encrypted bucket.

## Hand off

A clean ledger is ready for the classifier (`cadrumo-clasificar`).
