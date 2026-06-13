---
tags:
  - '#exec'
  - '#llm-client'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-llm-client-plan]]'
---

# `llm-client` `phase-1` `step-1`

Implemented the new LLM client package, additive settings, CLI surface, and the
required verification suite for issue `#21`.

- Modified: `src/aeat/config.py`
- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `env/.env.example`
- Modified: `pyproject.toml`
- Created: `src/aeat/adapters/outbound/llm/`
- Created: `src/aeat/entrypoints/cli/llm/`

## Description

Added a new `aeat.adapters.outbound.llm` public package that centralizes provider selection,
prompt lookup, caching, usage recording, translation, and bulk translation
behind `LLMClient`.

Implemented strict pydantic request, response, prompt, cache, usage, and
translation records together with an `LLMError` hierarchy rooted in
`aeat.core.errors.AeatError`.

Implemented provider adapters under `src/aeat/adapters/outbound/llm/_providers/`, including a
real Anthropic adapter, hosted-provider HTTP adapters for OpenAI and Gemini, a
local fallback adapter, and a deterministic `_FakeAdapter` used by unit tests.

Added additive LLM settings for provider selection, models, API keys, cache
and usage paths, timeout, and retries. API keys are represented as
`SecretStr`.

Wired `aeat llm` Typer commands for completion, translation, cache stats and
pruning, and usage summaries into the root CLI.

Added colocated smoke, unit, and opt-in live tests covering cache behavior,
prompt registry lookup, usage recorder persistence, provider error mapping,
strict model round-trips, and translation behavior.

## Tests

Validated the implementation with `just lint`, `just typecheck`, `just test`,
and `just hooks` on Windows. The opt-in live Anthropic test remains gated by
`AEAT_LIVE_TESTS=1` and was not exercised in the default local run.
