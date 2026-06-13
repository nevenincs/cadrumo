---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S338'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S338 - Close AFR-236 for filing amendments

Scope: close `AFR-236` for `src/aeat/domain/filing/_complementaria_repository.py`
with signals `secure-object, manifest-bucket, plain-file`, target `runtime-default`,
and owner `W12.P21.S84`.

## Description

- Audited `ModeloAmendmentRepository` for runtime-default secure storage enrollment.
- Confirmed the repository resolves explicit or active profile bucket ids through the
  filing runtime helper and constructs secure objects via `secure_object_repository_for_bucket`.
- Confirmed amendment payloads are wrapped as AUDIT `Envelope` records before storage and
  that the logical path APIs expose only `db://secure_objects` diagnostic markers.
- Verified unsafe amendment ids are rejected before logical marker, load, save, and delete
  operations.
- Verified existing real-behavior tests cover encrypted roundtrip, encrypted-at-rest
  payload absence, classification mismatch refusal, and mutated-payload load failure.
- Closed `W12.P26.S338` through `vaultspec-core vault plan step check` and updated
  the `AFR-236` register status to `closed`.

## Outcome

`AFR-236` is closed without a production code edit. The amendment repository is already
runtime-default enrolled and persists AUDIT amendment records through the encrypted
secure-object runtime rather than plaintext JSON files.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/filing/_complementaria_repository.py src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/application/filing/test_complementaria_repository.py src/aeat/domain/filing/test_secure_storage_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/domain/filing/test_amendment_roundtrip.py src/aeat/application/filing/test_complementaria_repository.py src/aeat/domain/filing/test_secure_storage_roundtrip.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "ModeloAmendmentRepository complementaria filing amendments secure_object_repository_for_bucket AUDIT encrypted runtime bucket" --type code --port 8766 --max-results 8`

## Notes

No code change was justified for this step. The remaining plan-tracking concern is
separate: some already-checked W12.P26 rows still show pending AFR register entries
and should be reconciled in a tracking repair step rather than hidden inside S338.
