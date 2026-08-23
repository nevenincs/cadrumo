---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4e1e6a4fb71d3f1dec64c7136a8b482caf50bc8b421fe101367372a737759442'
step_id: 'S33'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-inventory-casilla-mapping-adr]]"
---

# decide revision windows, activity aggregation, sign, rounding, missing-ledger behavior, and caller override policy

## Scope

- `.vault/adr/2026-08-23-inventory-casilla-mapping-adr.md`

## Description

- Limit the first authoritative projection to Modelo 100 ejercicio 2025.
- Preserve taxpayer-year-activity grain until registry-authorized aggregation.
- Require complete, readable, provenance-bearing valuation and acquisition-cost state.
- Fail closed on absence, inconsistency, discontinuity, conflict, or unreadable storage.
- Give a complete ledger exclusive ownership and refuse caller replacement.

## Outcome

The accepted ADR defines the inventory source authority boundary and its fail-closed behavior. Manual input remains available only when no complete inventory source is connected and cannot masquerade as source resolution.

## Notes

Earlier revisions, unsupported regimes, and incomplete production-cost semantics remain outside the authorized connection.
