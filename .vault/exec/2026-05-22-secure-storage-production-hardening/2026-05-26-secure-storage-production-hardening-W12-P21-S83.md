---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S83'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-production-hardening-W12-P20-summary]]'
  - '[[2026-05-26-active-profile-storage-runtime-classification-closeout-audit]]'
  - '[[2026-05-26-secure-storage-production-hardening-w12-p21-s83-review-audit]]'
---



# `secure-storage-production-hardening` `W12.P21.S83`

Migrated workflow state, workflow run, and bucket-event repositories to runtime-owned secure-object factories.

## Changes

- Replaced production `SecureObjectRepository()` defaults in `WorkflowStateRepository`, `WorkflowRunRepository`, and `BucketEventHistoryRepository` with lazy runtime resolution through `inspect_bucket_storage_runtime`.
- Removed the injectable reset-event emitter from `WorkflowStateRepository` so `reset_workflow_state` always uses the production `workflow_state.reset` audit event route before deletion.
- Kept explicit repository injection available for narrow callers that already own a repository, while making the default path active-bucket scoped.
- Resolved the bucket-event default path through the core active-bucket pointer instead of importing application workflow state into the domain bucket layer.
- Migrated workflow state, workflow run, resume, profile health, and bucket-event roundtrip tests away from `AEAT_DATABASE_URL` environment wiring and direct secure-object construction where they intersect this step.
- Preserved anti-tautology proof coverage by tampering encrypted records after a real save and asserting concrete validation errors on load.
- Reworked the reset-state emit-before-delete proof to corrupt the real bucket-event catalogue through the secure-object API, then verify the workflow-state fingerprint remains readable after the production event load fails.
- Removed the new broad exception/noqa pattern from the bucket-event tamper proof and did not add suppressive `noqa` or `pragma` markers.

## Validation

- `uv run --no-sync ruff check src/aeat/application/workflow/_persistence.py src/aeat/domain/buckets/_event_repository.py src/aeat/application/workflow/test_persistence.py src/aeat/application/workflow/test_state_persistence_roundtrip.py src/aeat/domain/buckets/test_event_history_roundtrip.py src/aeat/application/workflow/test_profile_health.py src/aeat/application/workflow/test_resume.py src/aeat/application/workflow/test_run_persistence_roundtrip.py`
- `uv run --no-sync pytest src/aeat/application/workflow/test_persistence.py src/aeat/application/workflow/test_state_persistence_roundtrip.py src/aeat/domain/buckets/test_event_history_roundtrip.py src/aeat/application/workflow/test_profile_health.py src/aeat/application/workflow/test_resume.py src/aeat/application/workflow/test_run_persistence_roundtrip.py -q`
- `uv run --no-sync ruff check src/aeat/application/workflow src/aeat/domain/buckets`
- `uv run --no-sync pytest src/aeat/application/workflow src/aeat/domain/buckets -q`
- `rg -n "SecureObjectRepository\(" src/aeat/application/workflow src/aeat/domain/buckets -g "*.py" -g "!test_*.py"`
- `rg -n "monkeypatch|setenv|AEAT_DATABASE_URL|noqa|pragma" src/aeat/application/workflow/_persistence.py src/aeat/domain/buckets/_event_repository.py src/aeat/application/workflow/test_persistence.py src/aeat/application/workflow/test_state_persistence_roundtrip.py src/aeat/domain/buckets/test_event_history_roundtrip.py src/aeat/application/workflow/test_profile_health.py src/aeat/application/workflow/test_resume.py src/aeat/application/workflow/test_run_persistence_roundtrip.py`
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

## Notes

- The production search found no remaining direct `SecureObjectRepository()` construction in the targeted non-test workflow and bucket-domain files.
- The suppressor search found one pre-existing `pragma` on i18n cache invalidation in `WorkflowStateRepository`; S83 did not introduce it. The block logs at debug level with `exc_info=True` and intentionally prevents cache invalidation import failure from blocking persistence.

## Review

The mandatory S83 review found that the reset-state test used a synthetic emitter and that the repository constructor exposed that bypass as a public seam. The seam was removed, and the proof now drives a real bucket-event-history persistence failure through the secure-object API while asserting the workflow-state row remains readable.
