---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S139]]'
---

# `secure-storage-production-hardening` `W12.P26.S139` Review

## S139-001 | PASS | LLM usage recorder default root now flows through centralized settings

The reviewed recorder persists redacted usage records through the active-bucket secure-object repository under `SensitivityClass.DIAGNOSTIC`. The remaining S139 gap was the default logical root: direct `UsageRecorder()` construction used `PROJECT_ROOT / "var" / "llm-usage"` instead of the centralized settings surface.

The default now uses `load_settings().aeat_llm_usage_dir`, preserving explicit `root_dir` overrides while enrolling direct construction in the project settings contract. This mirrors the S137 cache hardening and keeps test/runtime overrides effective through the canonical settings accessor.

The storage failure message no longer embeds the logical path. The path remains returned on success as an operator display value, but failure text is generic and retains the original `OSError` through exception chaining.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/test_usage.py src/aeat/adapters/outbound/llm/test_usage_roundtrip.py` passed with 3 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/test_usage.py src/aeat/adapters/outbound/llm/test_usage_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "llm_usage or usage_default_root or usage_recorder"` passed with 5 selected tests.
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/test_locale_coverage_hardened_errors.py` passed with 81 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/llm/_usage.py src/aeat/adapters/outbound/llm/test_usage.py src/aeat/adapters/outbound/llm/test_usage_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with only the existing `PLAN022` warning.
- Source scan found no direct `PROJECT_ROOT`, direct `Settings()`, hard-coded `var/llm-usage`, `logical path` failure text, `# noqa`, pragma, `type: ignore`, `except Exception`, or `except BaseException` in the S139 code/test slice.

Disposition: close `AFR-037` as `runtime-default`.

## S139-002 | CRITICAL | RESOLVED | Partial NoActiveProfileError relocation broke pytest import

During S139 validation, pytest failed before collecting the usage tests because project conftest imported `aeat.application.workflow`, whose package surface still imported `NoActiveProfileError` from `workflow._errors` after the workflow-local class had been removed. This was an import-time project break, and it also intersected the exception-hierarchy/registry mandate.

Resolution: `workflow._errors` now explicitly re-exports the relocated core `NoActiveProfileError` using a redundant alias, preserving legacy import sites without recreating a duplicate application error class. The stale application registry row for the removed workflow-local class is gone; the exported error binds to the core registry row `REFUSED_NO_ACTIVE_PROFILE`.

Validation:

- `uv run --no-sync pytest -q src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/test_locale_coverage_hardened_errors.py` passed with 81 tests.
- `uv run --no-sync ruff check src/aeat/application/workflow/_errors.py src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/core/errors/registry/_application.py` passed as part of the scoped ruff gate.

## S139-003 | LOW | RESOLVED | Workflow package docstring still described NoActiveProfileError as workflow-owned

The first relocation repair preserved the runtime export but left `workflow.__init__` documentation saying `NoActiveProfileError` was one of the workflow-local subclasses. That was stale after the core relocation.

Resolution: the package docstring now describes `NoActiveProfileError` as a core-owned re-export alongside the workflow-local error taxonomy.
