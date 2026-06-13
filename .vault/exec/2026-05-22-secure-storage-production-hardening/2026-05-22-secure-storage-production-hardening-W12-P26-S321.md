---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S321'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S321 bucket event repository

## Scope

- `src/aeat/domain/buckets/_event_repository.py`

## Description

- Audited `domain.buckets._event_repository` against the target `runtime-default` (owner `W12.P21.S83`).
- Confirmed `BucketEventHistoryRepository.__init__` routes through the canonical runtime helper `secure_object_repository_for_active_bucket` when no `objects=` override is passed; no parallel constructor path opens its own SecureObjectRepository.
- Confirmed the `secure-object`, `runtime`, and `active-profile` signals are all accounted for by this single delegation: the runtime helper resolves the active-profile bucket id and constructs a `SecureObjectRepository` bound to it, so every event read / write is automatically bucket-scoped against the active profile.
- Confirmed the `manifest-bucket` signal is appropriate: the encrypted-SQL persistence row lives under the active bucket's manifest directory; the repository never reads or writes outside that scope.
- Persistence delegation uses the standard `SecureObjectWrite` envelope and the `save` / `update` repository API; no shadow write path, no direct SQL escape from the secure-object boundary.
- Hardened `BucketEventHistoryRepository.load` so secure-object classification/version failures, payload schema drift, inner envelope classification drift, and inner schema-version drift surface as structured AEAT errors with registered translation keys.
- Extended the real SQLite roundtrip tests to mutate persisted secure-object payloads and assert the runtime-backed repository rejects drift without fakes, stubs, monkeypatches, or shadow business logic.

## Outcome

- AFR-219 closed: the runtime-default secure-object routing is correctly delegated through the canonical helper, and the load boundary now preserves structured integrity diagnostics for all observed persisted-drift cases.
- Validation passed: `ruff check` for the touched bucket files and runtime-migration/sensitivity tests; bucket event roundtrip tests; runtime migrated bucket-event selection; repository sensitivity class tests; locale audit via `python -m aeat.locales audit`; vaultspec RAG searches for bucket-event runtime routing and namespace registry grounding.

## Notes

- The shared plan already had `AFR-219` and `W12.P26.S321` marked closed when this hardening pass ran; no plan checkbox edit was needed for this slice.
- `src/aeat/domain/transactions/_models.py` was dirty from concurrent model-split work and was intentionally left untouched.
