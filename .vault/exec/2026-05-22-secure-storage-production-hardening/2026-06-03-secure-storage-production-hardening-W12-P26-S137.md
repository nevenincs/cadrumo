---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S137'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s137-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S137`

Closed `AFR-035` for the LLM encrypted cache.

## Description

- Reviewed `src/aeat/adapters/outbound/llm/_cache.py` against the `secure-object`, `plain-file`, and `remote-provider` scanner signals.
- Confirmed cache entries are persisted as encrypted secure objects under the `aeat.outbound.llm.cache` namespace with `SensitivityClass.DIAGNOSTIC` and redaction before write.
- Replaced the direct `PROJECT_ROOT / "var" / "llm-cache"` default with the centralized, override-aware `load_settings().aeat_llm_cache_dir` setting.
- Added real behavior coverage proving direct `LLMCache()` construction honors `aeat_llm_cache_dir` while still avoiding plaintext cache-file materialization.
- Closed `W12.P26.S137` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-035` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/test_cache.py src/aeat/adapters/outbound/llm/test_cache_roundtrip.py src/aeat/adapters/outbound/llm/test_redaction.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/test_cache.py src/aeat/adapters/outbound/llm/test_cache_roundtrip.py src/aeat/adapters/outbound/llm/test_redaction.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "llm_cache or cache_default_root"`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/llm/_cache.py src/aeat/adapters/outbound/llm/test_cache.py src/aeat/adapters/outbound/llm/test_cache_roundtrip.py src/aeat/adapters/outbound/llm/test_redaction.py src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `rg -n "PROJECT_ROOT|Settings\(\)|var/llm-cache|# noqa|pragma|type: ignore" src/aeat/adapters/outbound/llm/_cache.py src/aeat/adapters/outbound/llm/test_cache.py`
- `git diff --check -- src/aeat/adapters/outbound/llm/_cache.py src/aeat/adapters/outbound/llm/test_cache.py`

## Notes

The plan check still reports only `PLAN022` for non-monotonic canonical identifiers in document order.

The `rg` source scan intentionally returned no matches for direct project-root defaults, direct `Settings()` construction, pragma suppressions, noqa suppressions, or type-ignore duct tape in the S137 source and test files.

During validation, an initial test used `Settings()` implicitly and failed because it bypassed `override_settings`. The production change was corrected to use `load_settings()`, the project runtime settings accessor.
