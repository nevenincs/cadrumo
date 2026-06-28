---
tags:
  - "#adr"
  - "#llm-client"
date: "2026-04-12"
modified: '2026-04-12'
related:
  - "[[2026-04-12-llm-client-research]]"
  - "[[2026-04-12-base-module-structure-adr]]"
  - "[[2026-04-12-base-module-structure-reference]]"
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
- The package must stay buildable before issue `#20` merges.
- The project wants one real provider adapter now, not a sprawling matrix of
  partially-tested SDK integrations.
- The public surface must remain importable from `aeat.adapters.outbound.llm` only.

## Constraints

- All boundary-crossing types must be strict pydantic v2 models.
- API keys must use `SecretStr` and must never be logged or serialized in the
  public models.
- Provider SDK imports are allowed only under `src/aeat/adapters/outbound/llm/_providers/`.
- Settings changes must stay additive in `src/aeat/config.py`.
- The branch must not hard-import `aeat.core.i18n` because issue `#20` is still in
  flight.

## Implementation

- Create a new `src/aeat/adapters/outbound/llm/` subpackage with:
  - public typed exports in `__init__.py`,
  - strict pydantic request / response / cache / usage / translation models,
  - a single async-first `LLMClient.complete()` entry point,
  - a `PromptRegistry`,
  - an on-disk `LLMCache`,
  - an append-only `UsageRecorder`,
  - `Translator` and `BulkTranslator` built on top of `LLMClient`.
- Use Anthropic as the primary production adapter with the official Python SDK.
- Include a real `_FakeAdapter` for deterministic unit tests and a local
  fallback adapter for experimental offline use.
- Keep `OPENAI` and `GEMINI` in the public provider enum and provider factory
  contract so the package surface matches the intended provider matrix, but do
  not make them the primary path for this issue.
- Render prompts with standard-library formatting instead of Jinja2.
- Persist cache entries under `var/llm-cache/` and usage JSONL files under
  `var/llm-usage/`.
- Add a local compatibility shim with `TODO #20` markers for the future
  `Language` / `Translatable` contract.

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

## Consequences

- Anthropic becomes the default hosted dependency for v1, so live verification
  will initially cover Anthropic only.
- OpenAI and Gemini remain part of the public provider matrix but are not the
  project default in this branch.
- The package intentionally does not expose streaming, fine-tuning, or UI-level
  usage browsing in v1.
- A follow-up after issue `#20` merges must replace the local compatibility shim
  with the real `aeat.core.i18n` imports.
