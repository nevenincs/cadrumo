---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S139'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s139-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S139`

Closed `AFR-037` for the LLM usage recorder.

## Description

- Reviewed `src/aeat/adapters/outbound/llm/_usage.py` against the `secure-object` and `plain-file` scanner signals.
- Confirmed usage records are persisted through the active-bucket secure-object runtime under `aeat.outbound.llm.usage` with `SensitivityClass.DIAGNOSTIC` redaction.
- Replaced the direct `PROJECT_ROOT / "var" / "llm-usage"` default with the centralized, override-aware `load_settings().aeat_llm_usage_dir` setting.
- Removed logical path interpolation from the public storage-failure error message while preserving the chained `OSError`.
- Added real behavior coverage proving direct `UsageRecorder()` construction honors `aeat_llm_usage_dir`, returns the logical display path, and still avoids plaintext usage directory materialization.
- Repaired an adjacent import-time registry failure caused by the partial `NoActiveProfileError` relocation: `workflow._errors` now explicitly re-exports the core error, and the application registry no longer declares a row for the removed workflow-local class.
- Closed `W12.P26.S139` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-037` is closed as `runtime-default`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/test_usage.py src/aeat/adapters/outbound/llm/test_usage_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/test_usage.py src/aeat/adapters/outbound/llm/test_usage_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "llm_usage or usage_default_root or usage_recorder"`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_active_profile_resolution.py src/aeat/test_locale_coverage_hardened_errors.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/llm/_usage.py src/aeat/adapters/outbound/llm/test_usage.py src/aeat/adapters/outbound/llm/test_usage_roundtrip.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `rg -n "PROJECT_ROOT|Settings\(\)|var/llm-usage|logical path|# noqa|pragma|type: ignore|except Exception|except BaseException" src/aeat/adapters/outbound/llm/_usage.py src/aeat/adapters/outbound/llm/test_usage.py`
- `git diff --check -- src/aeat/adapters/outbound/llm/_usage.py src/aeat/adapters/outbound/llm/test_usage.py`

## Notes

The plan check still reports only `PLAN022` for non-monotonic canonical identifiers in document order.

The `rg` source scan intentionally returned no matches for direct project-root defaults, direct `Settings()` construction, hard-coded `var/llm-usage`, public logical-path error text, pragma/noqa/type-ignore suppression, or broad exception catches in the S139 source and test files.

The workflow error relocation repair was included because pytest could not import the project conftest without it. It is adjacent to the user's exception-hierarchy mandate, not part of LLM usage persistence itself.
