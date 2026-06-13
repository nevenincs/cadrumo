---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` Code Review

S34-PASS-001 | PASS | No S34 secure-storage degradation diagnostics findings remain
Reviewed the W04.P08.S34 changed scope for secure-storage read degradation propagation. The source-mesh helper emits typed `CalculationSourceDiagnostic` entries with `reason='storage_degraded'`, uses `tr()` for the diagnostic message, logs the typed degradation at debug level with exception info, and the resolver call sites catch only `ClassificationError`, `DecryptionError`, and `EnvelopeVersionError`. Source resolution merging preserves diagnostics, and the new storage-degradation coverage includes a real encrypted-store unreadable-row path without mocks, monkeypatches, fakes, stubs, skips, or xfails.

Validation: `uv run ruff check` on the S34 changed files passed. `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py -q` passed with 11 tests. A broader related-suite probe also found three non-S34 registry/profile fixture failures in existing tests: `test_modelo_390_prefill_compares_annual_totals_to_persisted_periodic_observations`, `test_calculate_modelo_revision_consumes_borrador_snapshot_through_application_service`, and `test_calculate_modelo_revision_precedence_keeps_caller_above_borrador_and_backend`.
