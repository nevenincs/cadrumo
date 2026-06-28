---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S348'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S348 - Close AFR-246 for justificante repository

Scope: close `AFR-246` for `src/aeat/domain/justificante/_repository.py` with signal
`secure-bound`, target `runtime-default`, and owner `W12.P21.S84`.

## Description

- Audited `JustificanteRepository` for secure-bound runtime-default enrollment.
- Confirmed the repository inherits runtime-owned secure-object construction from
  `SecureBoundRepository`.
- Confirmed namespace, AUDIT sensitivity, schema version, typed payload model, and CSV
  identifier extraction are declared on the concrete repository.
- Verified encrypted database roundtrip, classification refusal, id listing, deletion,
  unsafe identifier rejection, and vocabulary stability coverage.
- Reused declared AEAT URL fixture helpers in justificante tests instead of raw Sede or
  WLPL URL literals.
- Closed `W12.P26.S348` through `vaultspec-core vault plan step check` and updated the
  `AFR-246` register status to `closed`.

## Outcome

`AFR-246` is closed. The justificante repository is a runtime-default secure-bound
repository over encrypted AUDIT metadata. No production code change was required; the
test updates tighten source hygiene around AEAT literals.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/justificante/_repository.py src/aeat/domain/justificante/test_repository.py src/aeat/domain/justificante/test_secure_storage_roundtrip.py src/aeat/domain/justificante/test_vocabulary_stable.py src/aeat/tests/aeat_literal_fixtures.py`
- `uv run --no-sync pytest -q src/aeat/domain/justificante/test_repository.py src/aeat/domain/justificante/test_secure_storage_roundtrip.py src/aeat/domain/justificante/test_vocabulary_stable.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `uv run --no-sync vaultspec-rag search "JustificanteRepository SecureBoundRepository AUDIT runtime-default secure-bound secure object encrypted metadata" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "justificante secure storage roundtrip SecureBoundRepository active bucket runtime AUDIT envelope tests" --type code --port 8766 --max-results 8`

## Notes

This step deliberately avoided S298 and the recently active filing rows. The S348
production repository already conformed to the runtime-default secure-bound contract.
