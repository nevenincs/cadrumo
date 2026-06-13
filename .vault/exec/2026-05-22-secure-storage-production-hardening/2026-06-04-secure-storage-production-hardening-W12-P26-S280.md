---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S280'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S280 - Close AFR-178 for workflow errors

Scope: close `AFR-178` for `src/aeat/application/workflow/_errors.py` with
signals `active-profile, manifest-bucket, master-key`, target `manifest-discovery`,
and owner `W12.P22.S90`.

## Description

- Audited the workflow exception hierarchy for storage and manifest side effects.
- Confirmed the file declares typed exceptions only and performs no manifest, bucket,
  settings, repository, SQL, remote-provider, or master-key operation.
- Verified workflow errors derive from AEAT core error bases and have registry rows.
- Confirmed the file has no `except` handlers and therefore no local swallowing path.
- Repaired two application error-registry suggestions so they parse as `aeat` CLI
  commands under the shared registry contract.
- Ran vaultspec RAG semantic search for duplicate workflow error hierarchy surfaces.
- Closed `W12.P26.S280` through `vaultspec-core vault plan step check` and updated
  the `AFR-178` register status to `closed`.

## Outcome

`AFR-178` is closed as manifest-discovery taxonomy evidence. No production code
change was required for `src/aeat/application/workflow/_errors.py`; the only code
repair in this slice was the registry suggestion contract cleanup discovered by the
gate.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_errors.py src/aeat/core/errors/registry/_application.py src/aeat/application/workflow/test_engine.py src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_engine.py src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync python -c "from aeat.application.workflow._errors import WorkflowError, WorkflowInputMismatchError; from aeat.core.errors import AeatError, CoreValidationError, get_registered_error_code; assert issubclass(WorkflowError, AeatError); assert issubclass(WorkflowInputMismatchError, CoreValidationError); assert get_registered_error_code(WorkflowError) is not None; assert get_registered_error_code(WorkflowInputMismatchError) is not None"`
- `uv run --no-sync vaultspec-rag search "workflow errors exception hierarchy active profile manifest bucket master key registry" --type code --port 8766 --max-results 8`

## Notes

The scanner signals are retained in the plan record because they document why the
file was reviewed, but the implementation disposition is taxonomy-only.
