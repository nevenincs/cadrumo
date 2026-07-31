---
tags:
  - "#adr"
  - "#llm-client"
date: '2026-04-12'
modified: '2026-07-17'
body_hash: 'sha256:4eb59516ad60bdba6b3fdfcd08fa2d686531c0e0a1c062054571b0cb99a118e9'
related:
  - "[[2026-04-12-llm-client-research]]"
---

# `llm-client` adr: `async-llm-client-with-anthropic-primary` | (**status:** `accepted`)

## Problem Statement

Issue `#21` needs a single, typed LLM integration surface for AEAT workflows.
The package must support prompt execution, caching, usage recording, and
translation while preserving the project-wide constraints: strict pydantic v2
records, additive settings, Typer CLI wiring, colocated tests, and no provider
SDK imports outside the LLM provider chokepoint.

## Considerations

- The LLM package will be consumed by translation work immediately and by
  downstream extraction issues later.
- Spanish is the authoritative language for AEAT legal and tax content.
- The package uses the canonical shared internationalisation contract.
- Every provider named by the factory must have a real adapter; enum-only or
  placeholder provider entries are prohibited.
- The public surface must remain importable from `cadrumo.adapters.outbound.llm` only.

## Constraints

- All boundary-crossing types must be strict pydantic v2 models.
- API keys must use `SecretStr` and must never be logged or serialized in the
  public models.
- Provider SDK imports are allowed only under `src/cadrumo/adapters/outbound/llm/_providers/`.
- Settings changes must stay additive in `src/cadrumo/core/config.py`.
- `cadrumo.core.i18n` is the sole `Language` / `Translatable` authority.

## Implementation

- Create a new `src/cadrumo/adapters/outbound/llm/` subpackage with:
  - public typed exports in `__init__.py`,
  - strict pydantic request / response / cache / usage / translation models,
  - a single async-first `LLMClient.complete()` entry point,
  - a `PromptRegistry`,
  - an on-disk `LLMCache`,
  - an append-only `UsageRecorder`,
  - `Translator` and `BulkTranslator` built on top of `LLMClient`.
- Use Anthropic as the primary production adapter with the official Python SDK.
- Support the hosted provider adapters and the real local
  Ollama-compatible adapter behind the same typed provider contract.
- Keep `OPENAI` and `GEMINI` in the public provider enum and provider factory
  contract so the package surface matches the intended provider matrix, but do
  not make them the primary path for this issue.
- Render prompts with standard-library formatting instead of Jinja2.
- Persist cache entries under `var/llm-cache/` and usage JSONL files under
  `var/llm-usage/`.
- Use the shared `cadrumo.core.i18n` `Language` / `Translatable` contract
  directly; no local duplicate, shim, or deferred replacement is permitted.

## Rationale

- Anthropic is the best fit for the primary provider because the available
  public evidence is strongest for multilingual Spanish performance and the
  product positioning aligns with long-form reasoning on document-heavy tasks.
- A single production provider plus a local fallback keeps the implementation
  tractable while still exposing the provider matrix that downstream features
  expect.
- Standard-library prompt rendering is sufficient for the current prompt seeds
  and easier to audit than a more expressive templating language.
- A single `LLMClient` chokepoint guarantees that caching, retries, cost
  estimation, and usage accounting cannot be bypassed accidentally.
- Provider-neutral tests exercise real cache, usage, request, response, and
  local HTTP boundary behavior. Hosted-provider verification is opt-in and
  fails honestly when enabled; the architecture does not prescribe a
  synthetic production adapter.

## Consequences

- Anthropic is the default hosted provider. Anthropic, OpenAI, Gemini, and the
  local Ollama-compatible provider each resolve to a real adapter; live
  verification is provider-specific and explicit.
- The package intentionally does not expose streaming, fine-tuning, or UI-level
  usage browsing in v1.
- The implementation imports `cadrumo.core.i18n` directly and owns no
  transitional internationalisation surface.
