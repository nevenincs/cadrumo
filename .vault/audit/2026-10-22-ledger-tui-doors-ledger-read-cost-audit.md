---
tags:
  - '#audit'
  - '#ledger-tui-doors'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:dbad38fca6e212d02129a22c9450b4013ef609383b8187244ff7ab4f4058c39f'
related: []
---

# `ledger-tui-doors` audit: `ledger read cost at 30,000 transactions`

## Scope

The CPU cost of every ledger read the TUI Records screens call, measured on a real encrypted profile seeded with 30,000 transactions over ten filing years, 3,000 invoices and proportionate evidence, rules and registers. Measured by `dev/ci/tests/test_ledger_tui_reads_benchmark.py` and `dev/ci/tests/test_ledger_list_page_benchmark.py`, with cProfile breakdowns of the transaction and invoice decode paths. Process CPU time throughout; wall time is advisory on a shared machine.

## Findings

### period-list-full-scan | high | a period-filtered ledger.list page decoded every transaction

Before `259fa27d74`, a period-filtered page cost about 13-15 CPU-s at p95 because `src/cadrumo/application/ledger/list_query.py` loaded the whole catalogue before filtering. Reading the period's date partition brought it to about 0.55 CPU-s at p95.

### reconciliation-all-pairs | high | workbench generation compared every invoice with every transaction

`suggest_reconciliations` in `src/cadrumo/domain/invoices/service.py` made 90 million pair checks at 3,000 invoices and 30,000 transactions; workbench generation cost about 118-146 CPU-s. An amount index with identical output brought it to about 20 CPU-s (`6a04698b3d`). When many records share one amount every true match is still built; limiting that would change output.

### repeated-full-loads | high | several reads loaded the whole catalogue more than once

At 30,000 rows `ledger.status` loaded it four times (about 41 CPU-s), `ledger.view` three times (about 30), `ledger.check` and `ledger.track` twice, and `history`, `participation` and `preflight` once each where an id or a period would have sufficed.

### per-row-readmission | high | every stored transaction is re-admitted on every read

One whole-catalogue load costs about 6.4 CPU-s after the per-row fixes (`87188cd7a6`, `c13616273b`, `54a2eb8d69`), about 212 microseconds per row. About 74% is re-validating each row through 78 wrapped validator calls: 53 per-field converters and checks (13 enum, 9 id, 8 decimal, 6 collection, 9 for three timestamps checked three times each, 8 others), 11 for the nested raw record validated separately in Python mode, and 14 whole-row checks including the derived-id re-hash, gross reconstitution and dated registry rules. Decryption itself is about 2% and the SQL fetch about 2%. Nothing is reused between reads, by design.

### invoice-catalogue-revalidation | medium | every invoice read validated the whole catalogue with repeated registry lookups

3,000 invoices made about 56,000 registry lookups per decode (about 7 CPU-s). Answering identical questions once per validation pass brought it to about 2 CPU-s (`26248514f3`). Viewing one invoice still validates all of them.

## Recommendations

- Decide whether authenticated stored records may skip admission re-derivations on read, and what stays checked; this is a trust-boundary decision for an ADR (per-row-readmission, invoice-catalogue-revalidation).
- Load once per read, read the period partition and read single rows by id under the existing latency decision (repeated-full-loads).
- Decide whether reconciliation suggestions may be limited or paged when true matches are numerous (reconciliation-all-pairs).
