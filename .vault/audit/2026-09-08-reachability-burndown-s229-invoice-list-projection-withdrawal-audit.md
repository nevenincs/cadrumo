---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:0d39d2a9d96c7d5ede0353f80615a77ddf1d837a10cec92bd19d0253d1f78dca'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S229]]"
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

## Scope

Reviewed W05.P12.S229 against the accepted canonical invoice structure decision, the bounded application-invoice diff, the live CLI list implementation, the cadence addition, and the Step Record. The review covered withdrawal of the unused flattened row projection and its self-tests while retaining the rich aggregate and repository consistency boundary.

## Findings

No findings.

Exact search finds no surviving `InvoiceListRow`, `list_invoice_rows`, or `list_unmatched_invoice_rows` declaration or consumer. The two removed tests exercised only those zero-consumer projections; they did not execute a shipped query or CLI entrypoint. Their sorting/filtering checks therefore did not protect the live invoice-list contract.

The canonical `Invoice` aggregate remains the sole rich invoice structure required by the accepted ADR. The live `ledger.invoice.list` command continues to load `InvoiceCatalogueRepository`, filter canonical invoices by `InvoiceKind`, and emit the established rich payload and text rows. Its unit and complementary non-unit suites remain recorded as 20 and 11 passing tests.

`verify_invoice_repository_links` remains production-used by the ledger check query and still loads both secure repositories before delegating to canonical link-consistency logic. Its two storage-boundary tests remain and pass. No duplicate projection, compatibility facade, hand-maintained inventory, or source dependency on tests/dev was introduced.

The cadence addition correctly generalises removal of zero-consumer flattened projections when the real entrypoint independently renders the canonical aggregate and retains behavioral coverage. The Step Record names precisely the three implementation/test files and cadence reference, records Ruff and all three focused lanes, and honestly records the exact detector's expected backlog exit. The 305 to 304 symbol movement with modules fixed at 51 and orphan tests fixed at four is consistent: only `list_invoice_rows` was in the reachable-module exact-symbol population, while the DTO/private projector were excluded by other detector rules.

## Recommendations

Approve W05.P12.S229 and close it through the plan workflow.
