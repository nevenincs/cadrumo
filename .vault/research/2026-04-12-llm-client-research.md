---
tags:
  - "#research"
  - "#llm-client"
date: "2026-04-12"
modified: '2026-04-12'
related:
  - "[[2026-04-12-base-module-structure-adr]]"
  - "[[2026-04-12-base-module-structure-reference]]"
---

# `llm-client` research: `provider-survey-and-package-fit`

Issue `#21` requires an async-first LLM client under `src/aeat/adapters/outbound/llm/` with strict
pydantic v2 records, a single public import chokepoint, on-disk caching, usage
logging, and a translation layer that must later integrate with the trilingual
contract from issue `#20`. This research compares provider options and captures
the repo-fit decisions that matter before implementation.

## Findings

### provider market snapshot on 2026-04-12

- Anthropic is the strongest primary candidate for document-heavy legal and tax
  reasoning. Public Anthropic material positions Claude Opus as the highest-
  capability tier and Claude Sonnet as the lower-latency, lower-cost tier.
- The issue text refers to `Claude Opus 4.6` and `Claude Sonnet 4.6`, but the
  official multilingual documentation currently exposes the Claude 4 / 4.1 /
  4.5 family naming. That mismatch should be treated as a moving-model-name
  problem, not as a reason to block the feature. The implementation should keep
  model names configurable via settings and request overrides.
- Anthropic provides the strongest directly published Spanish-language signal I
  found. Its multilingual support page reports Spanish performance at roughly
  `98%` of English across the Claude 4 family. That is not a Spanish legal-text
  benchmark, but it is the best provider-published evidence available for this
  issue's target language mix.
- OpenAI has the cleanest formal structured-output surface. The current OpenAI
  docs expose dedicated `Structured Outputs` support with JSON-schema-driven
  responses, strong tool calling, and favorable pricing for `GPT-4.1` relative
  to `GPT-4o`.
- Google Gemini has the lowest-cost high-volume path among the major hosted
  providers I surveyed. The Gemini 2.5 family also documents structured output
  with JSON Schema subsets and Pydantic examples, making it a credible second
  hosted option.
- Local runtimes are viable only as a constrained fallback. Ollama and
  llama.cpp both support local inference and schema-constrained outputs, but
  quality depends on the underlying model weights and local hardware, not on
  the runtime itself. There is no framework-level guarantee for Spanish legal
  fidelity, latency, or throughput.

### provider-by-provider trade-offs

- Anthropic:
  - Best fit for primary provider when correctness on long-form Spanish tax and
    legal text matters more than raw throughput.
  - Strong multilingual evidence for Spanish.
  - Native SDK available for Python, which fits the issue's requirement for a
    real provider adapter using the `anthropic` package.
  - Structured output is workable through tool schemas, but less explicit than
    OpenAI or Gemini's dedicated JSON-schema-first documentation.
- OpenAI:
  - Best backup path if the project later wants a stronger strict-schema
    workflow or cheaper text-only operation than Anthropic's top tier.
  - `GPT-4.1` has a favorable text-only cost profile and large context window.
  - `GPT-4o` remains a good multimodal alternative but is not needed for this
    feature's v1 text-only surface.
- Gemini:
  - Best low-cost hosted option for future high-volume extraction or translation
    batches once the project is comfortable with a second cloud provider.
  - Strong structured-output ergonomics and context-caching support.
  - No provider-published Spanish legal benchmark found.
- Local:
  - Worth keeping in the enum and adapter matrix so offline experimentation is
    possible.
  - Should be marked experimental in the ADR because correctness depends on the
    chosen local weights and workstation resources.

### implementation fit for this repo

- The package should isolate every provider import inside `src/aeat/adapters/outbound/llm/_providers/`.
  No other module should import `anthropic`, `openai`, `google`, `ollama`, or
  equivalent SDKs directly.
- All boundary records should be strict pydantic v2 models:
  `LLMRequest`, `LLMResponse`, `PromptDefinition`, `PromptRegistry`,
  `CachedEntry`, `UsageRecord`, `Translation`, and any private adapter payloads
  that cross the file or network boundary.
- Prompt rendering should use standard-library formatting rather than Jinja2 for
  v1. The initial prompts are simple, deterministic, and easier to audit with a
  `str.format_map`-style approach. This avoids another dependency and keeps
  prompt rendering easy to test.
- The cache should be content-addressed on disk under `var/llm-cache/`, keyed
  by provider, resolved model, prompt hash, and argument hash. Cache hits should
  bypass the provider adapter completely.
- Usage recording should be append-only JSONL under `var/llm-usage/` with one
  file per day. This satisfies the issue while staying independent of the
  future storage layer from issue `#10`.
- The translator should depend on a local compatibility shim for issue `#20`
  rather than importing `aeat.core.i18n` directly. That keeps this branch buildable
  before the i18n branch merges.

### recommended support matrix

- Supported in v1:
  - `ANTHROPIC`: primary hosted provider, real adapter, configurable model.
  - `LOCAL`: experimental fallback via local HTTP endpoint, off by default.
- Present in the public enum but not the default execution path:
  - `OPENAI`
  - `GEMINI`
- Rationale:
  - The enum should expose the provider matrix that downstream code will rely
    on, but the implementation effort should stay focused on one production
    adapter plus one offline fallback in this issue.

### non-goals confirmed by research

- No fine-tuning.
- No streaming token output in v1.
- No web UI for usage inspection.
- No direct imports from the future `aeat.core.i18n` package until issue `#20`
  lands on this branch.

### source URLs consulted

- Anthropic multilingual support:
  https://platform.claude.com/docs/en/build-with-claude/multilingual-support
- Anthropic tool-use / schema guidance:
  https://docs.anthropic.com/en/docs/build-with-claude/tool-use/implement-tool-use
- OpenAI GPT-4.1 model docs:
  https://developers.openai.com/api/docs/models/gpt-4.1
- OpenAI structured outputs guide:
  https://platform.openai.com/docs/guides/structured-outputs
- OpenAI GPT-4.1 announcement:
  https://openai.com/index/gpt-4-1/
- Gemini models overview:
  https://ai.google.dev/gemini-api/docs/models
- Gemini pricing:
  https://ai.google.dev/gemini-api/docs/pricing
- Ollama structured outputs:
  https://docs.ollama.com/capabilities/structured-outputs
- llama.cpp project:
  https://github.com/ggml-org/llama.cpp
