---
tags:
  - '#audit'
  - '#llm-client'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-llm-client-research]]'
  - '[[2026-04-12-llm-client-adr]]'
  - '[[2026-04-12-llm-client-plan]]'
---

# `llm-client` code review

No `CRITICAL` or `HIGH` findings were identified in the reviewed worktree.

public-api-001 | MEDIUM | Colocated tests import private `aeat.adapters.outbound.llm._providers` symbols instead of staying on the `aeat.adapters.outbound.llm` public surface
`src/aeat/adapters/outbound/llm/_test_client.py:14` imports `ProviderRequest` and `_FakeAdapter` from `aeat.adapters.outbound.llm._providers`, and `src/aeat/adapters/outbound/llm/_test_translation.py:13` imports `_FakeAdapter` from the same private package. This does not affect runtime callers, but it does violate the stated public-API discipline that callers should import from `aeat.adapters.outbound.llm` only. It also makes the test suite a consumer of internals that the package root explicitly says should stay hidden in `src/aeat/adapters/outbound/llm/__init__.py:3-4`.

docstrings-001 | LOW | Public symbols are typed, but the new public API does not consistently use Google-style docstrings
The typing discipline is strong across the new package, but the docstrings on exported/public entry points are mostly short summary lines rather than Google-style docstrings with structured sections. Representative examples include `src/aeat/adapters/outbound/llm/_client.py:52-53`, `src/aeat/adapters/outbound/llm/_cache.py:29-30`, `src/aeat/adapters/outbound/llm/_translator.py:24-32`, `src/aeat/adapters/outbound/llm/_usage.py:25-26`, and the CLI commands in `src/aeat/entrypoints/cli/llm/__init__.py:29-34`, `:48-54`, and `:75-79`. This misses rule `4` as written, even though the signatures themselves are typed.

## Rule Verification

- `1` single chokepoint rule: PASS. A direct SDK import search found provider SDK imports only in `src/aeat/adapters/outbound/llm/_providers/anthropic.py`.
- `2` pydantic v2 strict boundary types: PASS. `LLMRequest`, `LLMResponse`, `PromptDefinition`, `PromptRegistry`, `CachedEntry`, `UsageRecord`, `Translation`, `CacheKey`, `CacheStats`, `UsageSummary`, `ProviderRequest`, and `ProviderCompletion` all declare `ConfigDict(strict=True, ...)`.
- `3` API keys use `SecretStr` and are not exposed: PASS. `src/aeat/config.py:167-175` stores provider keys as `SecretStr | None`, `src/aeat/adapters/outbound/llm/_client.py:135-136` unwraps secrets only at adapter construction time, and no reviewed code logs or serializes the raw values. The masking behavior is covered in `src/aeat/adapters/outbound/llm/_test_client.py:108-118`.
- `4` typed signatures and Google-style docstrings on public symbols: FAIL. Typed signatures are present, but Google-style docstrings are not consistently used on the new public API.
- `5` errors inherit from `aeat.core.errors.AeatError`: PASS. `src/aeat/adapters/outbound/llm/_errors.py:8-33` roots the hierarchy at `LLMError(AeatError)`.
- `6` logging uses `aeat.core.logging.get_logger(__name__)`: PASS. The reviewed implementation uses `get_logger(__name__)` in `src/aeat/adapters/outbound/llm/_client.py:25-27`, and no conflicting logger construction was found in the changed files.
- `7` public API discipline: FAIL. Runtime-facing callers comply, but colocated tests in `src/aeat/adapters/outbound/llm/_test_client.py:14` and `src/aeat/adapters/outbound/llm/_test_translation.py:13` import private `aeat.adapters.outbound.llm._providers` symbols directly.
- `8` lint/typecheck/tests/hooks are green: PASS. `just lint`, `just typecheck`, `just test`, and `just hooks` all succeeded in this worktree on `2026-04-12`. The pytest run reported `114 passed, 1 skipped, 8 deselected`.

## Reviewed Files

- Tracked modified files reviewed: `env/.env.example`, `pyproject.toml`, `src/aeat/entrypoints/cli/__init__.py`, `src/aeat/config.py`, `uv.lock`.
- Untracked vault docs reviewed: `.vault/research/2026-04-12-llm-client-research.md`, `.vault/adr/2026-04-12-llm-client-adr.md`, `.vault/plan/2026-04-12-llm-client-plan.md`.
- New CLI files reviewed: `src/aeat/entrypoints/cli/llm/__init__.py`, `src/aeat/entrypoints/cli/llm/test_smoke.py`.
- All files under `src/aeat/adapters/outbound/llm/` reviewed, including provider adapters, models, cache, usage, translation helpers, and tests.

## Re-review Note

Re-review on `2026-04-12`: no remaining findings from the prior `MEDIUM` and `LOW` items.

- Prior `MEDIUM` finding `public-api-001`: RESOLVED. The colocated tests now import `ProviderRequest` and `_FakeAdapter` from `aeat.adapters.outbound.llm` rather than from `aeat.adapters.outbound.llm._providers`, as shown in `src/aeat/adapters/outbound/llm/_test_client.py:13-22` and `src/aeat/adapters/outbound/llm/_test_translation.py:12`. Rule `7` now passes for the reviewed worktree.
- Prior `LOW` finding `docstrings-001`: RESOLVED on the reviewed public entry points. The previously flagged public methods and CLI commands now use Google-style docstrings with `Args:` and `Returns:` sections where applicable, including `src/aeat/adapters/outbound/llm/_client.py`, `src/aeat/adapters/outbound/llm/_cache.py`, `src/aeat/adapters/outbound/llm/_translator.py`, `src/aeat/adapters/outbound/llm/_usage.py`, and `src/aeat/entrypoints/cli/llm/__init__.py`. Rule `4` now passes for the reviewed public entry points.
- Refreshed rule check summary: rules `1` through `8` pass in the current worktree.
- Refreshed verification commands: `just lint`, `just typecheck`, `just test`, and `just hooks` all passed again during this re-review. The pytest run again reported `114 passed, 1 skipped, 8 deselected`.
