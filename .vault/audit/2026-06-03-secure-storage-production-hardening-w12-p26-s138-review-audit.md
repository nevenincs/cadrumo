---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S138]]'
---

# `secure-storage-production-hardening` `W12.P26.S138` Review

## S138-001 | PASS | Gemini remote-provider adapter uses centralized settings and typed transport errors

The reviewed adapter is a remote HTTP provider boundary for Gemini `generateContent`. It already used `x-goog-api-key` headers rather than query-string API keys, but it still snapped the endpoint template through module-import-time `Settings()`. That bypasses `override_settings` and central runtime settings conventions.

The adapter now resolves the endpoint through `load_settings().aeat_llm_gemini_generate_content_template` at call time. This keeps the URL template under the central settings surface and makes test/runtime overrides effective without reimporting the module.

Transport failures are also normalized: `httpx.RequestError` is caught, logged at debug with traceback, and re-raised as `LLMProviderError` with a generic public message. This prevents raw provider-library exceptions from escaping the LLM adapter API while still preserving the root cause through exception chaining.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/_providers/test_gemini.py src/aeat/adapters/outbound/llm/_providers/test_base.py src/aeat/adapters/outbound/llm/test_client.py` passed with 11 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/llm/_providers/gemini.py src/aeat/adapters/outbound/llm/_providers/test_gemini.py src/aeat/adapters/outbound/llm/_providers/test_base.py src/aeat/adapters/outbound/llm/test_client.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` passed with only the existing `PLAN022` warning.
- Source scans found no direct `Settings()`, stale Gemini endpoint constant, query-string `params=`, `# noqa`, pragma, `type: ignore`, `except Exception`, or `except BaseException` in the S138 code/test slice.

Disposition: close `AFR-036` as `remote-mirror`.

## S138-002 | LOW | RESOLVED | Transport exception text could expose configured endpoint details

The first implementation raised `LLMProviderError(f"Gemini connection failure: {exc}")`. For `httpx.RequestError`, the string form can contain the requested URL. If an operator configured a nonstandard Gemini endpoint template containing sensitive query data, that could surface in operator-facing errors.

Resolution: the public exception message is now the generic `Gemini connection failure.`. The original exception remains chained for debug diagnostics, and the adapter logs the failure at debug with traceback.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/_providers/test_gemini.py src/aeat/adapters/outbound/llm/_providers/test_base.py src/aeat/adapters/outbound/llm/test_client.py` passed after the change.
