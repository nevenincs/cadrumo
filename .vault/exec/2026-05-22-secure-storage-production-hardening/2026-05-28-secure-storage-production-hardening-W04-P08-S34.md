---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S34'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-research]]'
---

# `secure-storage-production-hardening` `W04.P08.S34`

Propagated secure-storage degradation diagnostics from repository-backed source resolvers into the calculation source mesh.

- Modified: `src/aeat/application/aggregation/_source_mesh.py`
- Modified: `src/aeat/application/aggregation/_modelo_bindings.py`
- Modified: `src/aeat/application/aggregation/__init__.py`
- Modified: `src/aeat/application/invoices/_source_resolver.py`
- Modified: `src/aeat/application/calculations/_multi_year.py`
- Modified: `src/aeat/application/calculations/_relation_prefill.py`
- Modified: `src/aeat/application/modelo/_borrador_binding.py`
- Modified: `src/aeat/application/aggregation/test_source_mesh.py`
- Modified: `src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py`
- Reviewed: `.vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S34-review.md`

## Description

The source mesh now has a shared `storage_degradation_resolution` helper that converts known secure-storage read failures into typed `CalculationSourceDiagnostic` entries with `reason="storage_degraded"`. It uses the existing secure-object unreadable locale text through `tr()` and logs the original exception at debug level with exception info.

Repository-backed source resolvers for ledger aggregation, invoice catalogue, previous filings, relation prefill, and Modelo 100 borrador now catch only `ClassificationError`, `DecryptionError`, and `EnvelopeVersionError` at the storage-read boundary. Arbitrary exceptions still propagate.

## Tests

Validation covered helper-level diagnostic emission and debug logging, plus a real encrypted SQL storage corruption path through the IVA ledger source resolver and source mesh merge.

- `uv run ruff check src/aeat/application/aggregation/_source_mesh.py src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/aggregation/__init__.py src/aeat/application/invoices/_source_resolver.py src/aeat/application/calculations/_multi_year.py src/aeat/application/calculations/_relation_prefill.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py`
- `uv run pytest src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py -q`
- `git diff --check -- src/aeat/application/aggregation/_source_mesh.py src/aeat/application/aggregation/_modelo_bindings.py src/aeat/application/aggregation/__init__.py src/aeat/application/invoices/_source_resolver.py src/aeat/application/calculations/_multi_year.py src/aeat/application/calculations/_relation_prefill.py src/aeat/application/modelo/_borrador_binding.py src/aeat/application/aggregation/test_source_mesh.py src/aeat/application/aggregation/test_modelo_source_mesh_ledger.py .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md .vault/audit/2026-05-28-secure-storage-production-hardening-W04-P08-S34-review.md .vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-28-secure-storage-production-hardening-W04-P08-S34.md`

The reviewer also probed a broader related suite and recorded three pre-existing registry/profile fixture failures outside this S34 scope.
