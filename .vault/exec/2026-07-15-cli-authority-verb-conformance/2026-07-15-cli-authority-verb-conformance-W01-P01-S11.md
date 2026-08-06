---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:acdfd6b7343e1b12036ee7a83fff25ad78f9c612f57d94fe1b87f72963fda559'
step_id: 'S11'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Exercise dormant Modelo 369 verification through the real invoice repository Protocol boundary

## Scope

- `src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py`

## Description

- Ground the injected Modelo 369 invoice path with Vaultspec-RAG and exact symbol searches.
- Isolate the injected invoice catalogue from the ambient work, calculation, and transaction stores.
- Seed OSS evidence only in the injected real encrypted repository and prove the ambient catalogue stays absent.
- Exercise both public bucket calculation and legacy verification through the injected repository boundary.
- Run focused lint, real-behavior, static typing, duplicate-authority, and uncached import-graph gates.

## Outcome

The semantic search located the optional invoice port in the OSS/IOSS resolver and its legacy verification handoff. The strengthened positive M369 scenario now creates a second real SQLite engine and registry-bound `SecureObjectRepository` for invoice evidence while the active runtime retains work units, calculation revisions, transactions, and profile state. Three OSS invoices exist only in the injected catalogue, and the ambient `InvoiceCatalogueRepository` is asserted absent before calculation and after `verify_modelo_revision`. This makes the test fail if either consumer ignores injection and constructs from ambient state.

Ruff passed. The exact strengthened test passed once, and the complete five-test M369 module plus `test_no_parallel_oss_ioss_aggregator_exists` passed all six tests. Pyright reported zero errors and five pre-existing private test-support warnings. Ty reached one pre-existing diagnostic on the unchanged `source_provenance` call at line 532, where the file already carries a call-argument suppression; it reported no diagnostic in the changed two-store scenario. The fresh uncached import graph analyzed 3,421 files and 16,157 dependencies with all five contracts kept.

## Notes

No production implementation, default composition branch, fake, mock, stub, patch, monkeypatch, skip, or mirrored aggregation logic was introduced. The injected engine is disposed unconditionally.
