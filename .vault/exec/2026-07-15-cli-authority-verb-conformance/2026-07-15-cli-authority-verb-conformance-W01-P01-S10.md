---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S10'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Widen injected OSS and IOSS invoice-repository annotations while retaining the sole default composition path

## Scope

- `src/cadrumo/application/aggregation/_oss_ioss.py`

## Description

- Import the public domain `InvoiceCatalogueRepositoryProtocol` alongside the invoice value types.
- Type the two OSS/IOSS repository functions and source resolver constructor against the optional injected port.
- Retain the concrete persistence adapter solely for the explicit default composition branch.
- Align the module and injected-parameter documentation with the public repository port.
- Verify the narrowed surface with static checks, real OSS/IOSS and dormant M369 tests, and the uncached import graph.

## Outcome

The mandatory semantic query `OSS IOSS injected InvoiceCatalogueRepositoryProtocol optional repository concrete default construction resolver aggregation` located the public port and the verification-to-resolver handoff. Exact symbol searches confirmed three injected concrete annotations and one concrete construction in `oss_ioss_candidates_from_repositories`. The implementation now names `InvoiceCatalogueRepositoryProtocol` at every injected boundary while preserving the adapter import, explicit `None` branch, and sole `InvoiceCatalogueRepository(bucket_id=...)` default construction.

Ruff, ty, and pyright passed on the changed module. The real OSS/IOSS and dormant Modelo 369 suites passed all 22 tests against encrypted runtime storage. The uncached import graph analyzed 3,421 files and 16,155 dependencies with all five contracts kept.

## Notes

No runtime branch, constructor call, aggregation path, export, or import-linter waiver changed. Step S11 owns the distinct-store real-behavior coverage for the injected Protocol boundary.
