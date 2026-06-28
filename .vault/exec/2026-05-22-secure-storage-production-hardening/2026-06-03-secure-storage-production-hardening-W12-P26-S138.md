---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S138'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s138-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S138`

Closed `AFR-036` for the Gemini LLM provider adapter.

## Description

- Reviewed `src/aeat/adapters/outbound/llm/_providers/gemini.py` against the `remote-provider` scanner signal.
- Replaced the module-import-time `Settings()` endpoint-template snapshot with per-call `load_settings().aeat_llm_gemini_generate_content_template`.
- Preserved the hardened `x-goog-api-key` header posture and added local HTTP-server coverage proving the key does not move into the query string.
- Wrapped `httpx.RequestError` transport failures as `LLMProviderError` with debug logging and without embedding endpoint-bearing exception text in the public message.
- Added focused Gemini provider tests without mocks, monkeypatching, skips, xfails, pragma suppression, or `noqa` duct tape.
- Closed `W12.P26.S138` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-036` is closed as `remote-mirror`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/outbound/llm/_providers/test_gemini.py src/aeat/adapters/outbound/llm/_providers/test_base.py src/aeat/adapters/outbound/llm/test_client.py`
- `uv run --no-sync ruff check src/aeat/adapters/outbound/llm/_providers/gemini.py src/aeat/adapters/outbound/llm/_providers/test_gemini.py src/aeat/adapters/outbound/llm/_providers/test_base.py src/aeat/adapters/outbound/llm/test_client.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`
- `rg -n -F "Settings()" src/aeat/adapters/outbound/llm/_providers/gemini.py src/aeat/adapters/outbound/llm/_providers/test_gemini.py`
- `rg -n -F "_GEMINI_GENERATE_TEMPLATE" src/aeat/adapters/outbound/llm/_providers/gemini.py src/aeat/adapters/outbound/llm/_providers/test_gemini.py`
- `rg -n -F "params=" src/aeat/adapters/outbound/llm/_providers/gemini.py src/aeat/adapters/outbound/llm/_providers/test_gemini.py`
- `rg -n "# noqa|pragma|type: ignore|except Exception|except BaseException" src/aeat/adapters/outbound/llm/_providers/gemini.py src/aeat/adapters/outbound/llm/_providers/test_gemini.py`
- `git diff --check -- src/aeat/adapters/outbound/llm/_providers/gemini.py src/aeat/adapters/outbound/llm/_providers/test_gemini.py`

## Notes

The plan check still reports only `PLAN022` for non-monotonic canonical identifiers in document order.

The fixed-string `rg` scans intentionally returned no matches for direct `Settings()`, the removed module-level Gemini endpoint constant, query-string `params=`, and pragma/noqa/type-ignore/broad-exception suppression in the S138 source and test files.

Reviewer follow-up removed raw `httpx` exception text from the public `LLMProviderError` message so nonstandard endpoint templates cannot leak through operator-facing failures. The chained cause remains available for debug diagnostics.
