---
tags:
  - '#exec'
  - '#calculation-engine-foundations'
date: '2026-06-12'
step_id: 'S38'
related:
  - '[[2026-06-10-calculation-engine-foundations-plan]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
---

# W04.P12.S38 OSS/IOSS Live Projection

Scope: replace the M369 no-live-source stopgap with a live invoice-catalogue OSS/IOSS projection.

## Description

- Add optional OSS/IOSS projection axes to invoice records using the existing `OssIossRegime` and `TransactionKind` substrate enums.
- Add optional line-level OSS rate tier support so destination Member State IVA amounts can be stored and then validated by the OSS resolver.
- Project OSS/IOSS-tagged issued invoice lines from `InvoiceCatalogueRepository` into `OssIossLedgerCandidate` rows for the typed filing period.
- Wire `OssIossLedgerSourceResolver` into the live calculation mesh with the invoice repository instead of `candidates=()`.
- Keep explicit-candidate resolver mode for existing mesh-boundary and sync callers.
- Add a live M369 regression proving DE services, FR services, and DE goods invoices fold into Modelo 369 cuotas with no `oss_no_live_source` advisory.

## Outcome

`S38` is implemented. The previous blocker is resolved by the new OSS classification fields on invoices plus the line-level OSS rate tier; live M369 calculation no longer depends on preconstructed test-only candidates.

## Notes

The empty-catalogue advisory path remains for periods with declared OSS bindings but no projected OSS invoice candidates. The live proof uses real invoice catalogue persistence, real registry selectors, and the existing destination-rate validation.
