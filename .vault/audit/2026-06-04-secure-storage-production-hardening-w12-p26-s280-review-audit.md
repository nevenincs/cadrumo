---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S280-001 | PASS | Workflow error taxonomy false positive

The `W12.P26.S280` review found that `src/aeat/application/workflow/_errors.py`
declares typed workflow exception classes only. The active-profile, manifest-bucket,
and master-key scanner signals are names and docstring references in error taxonomy
copy, not executable storage access. The module does not read manifests, resolve
settings, open repositories, route SQL, touch master-key providers, or persist state.

Disposition: close `AFR-178` as manifest-discovery taxonomy evidence.

## S280-002 | PASS | AEAT exception hierarchy and registry binding

Workflow error classes derive from `AeatError`, `WorkflowError`, or the core
validation base where pydantic compatibility requires it. The concrete workflow
errors are registered in the shared error registry, including label ambiguity,
component wrapping, abort signalling, unhandled workflow wrapping, and input mismatch
errors.

## S280-003 | PASS | No swallowed exception path

This module contains no exception handlers. The relevant swallowed-exception policy
is enforced by callers, especially the workflow engine and profile-bucket scan
modules that wrap or log failures at their own boundaries.

## S280-004 | PASS | Duplication and validation

Vaultspec RAG clustered this slice with workflow error registry rows, active-profile
health, profile-bucket scan, and master-key storage errors. No duplicate workflow
error hierarchy requiring consolidation was found in this slice.

## S280-005 | PASS | Registry suggestion contract repair

The registry contract gate found two newly-invalid `default_suggestion` values in
the application error registry. Both were prose strings rather than parseable `aeat`
commands. The repair changed them to live CLI help commands while leaving localized
error messages unchanged.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_errors.py src/aeat/core/errors/registry/_application.py src/aeat/application/workflow/test_engine.py src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_engine.py src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync python -c "from aeat.application.workflow._errors import WorkflowError, WorkflowInputMismatchError; from aeat.core.errors import AeatError, CoreValidationError, get_registered_error_code; assert issubclass(WorkflowError, AeatError); assert issubclass(WorkflowInputMismatchError, CoreValidationError); assert get_registered_error_code(WorkflowError) is not None; assert get_registered_error_code(WorkflowInputMismatchError) is not None"`
- `uv run --no-sync vaultspec-rag search "workflow errors exception hierarchy active profile manifest bucket master key registry" --type code --port 8766 --max-results 8`
