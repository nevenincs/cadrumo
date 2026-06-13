---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P14.S47'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P14.S47 - Consolidate CSV and XLSX financial provider tabular extraction

Scope: Reduce the CSV/XLSX financial-provider row-projection clone behind the
existing provider boundary.

## Description

- Add a shared `ParsedTabularTransactionRow` projection in the CSV provider
  helper module that already owns the bank-layout catalogue.
- Move transaction id, booked date, value date, amount, currency, description,
  and counterparty projection into `_parse_tabular_transaction_row()`.
- Route both `CsvProvider.ingest()` and `XlsxProvider.ingest()` through that
  shared parser while preserving XLSX typed-cell parsing and worksheet-specific
  synthetic id prefixes.

## Outcome

CSV and XLSX ingestion now share the bank-layout row projection logic. XLSX
still owns workbook discovery, worksheet selection, and typed cell mapping; CSV
still owns byte decoding and dialect detection.

## Notes

`just audit-duplication` no longer reports a CSV/XLSX financial-provider clone.
It still reports other residual clone groups that belong to later W04.P14 rows
or unrelated shifted-worktree changes.
