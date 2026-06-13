---
tags:
  - "#plan"
  - "#llm-client"
date: "2026-04-12"
modified: '2026-04-12'
related:
  - "[[2026-04-12-llm-client-research]]"
  - "[[2026-04-12-llm-client-adr]]"
---

# `llm-client` `phase-1` plan

Implement the `src/aeat/adapters/outbound/llm/` subpackage, its CLI integration, additive
settings, and the required tests so downstream translation and extraction work
can rely on a single typed LLM surface.

## Proposed Changes

- Extend the package layout with a new `llm` subpackage following the locked
  `src/aeat/` conventions from the base-module-structure ADR.
- Add strict pydantic records, error hierarchy, prompt registry, cache, usage
  recorder, translator, and bulk translator.
- Add a real Anthropic provider adapter plus a deterministic `_FakeAdapter`.
- Wire a new `aeat llm` Typer subtree into the root CLI.
- Add additive LLM settings and align `env/.env.example` plus
  `tests/test_config.py`.
- Add colocated unit tests and one opt-in live Anthropic test.

## Tasks

- `Phase 1: package and provider foundation`
  1. Create `src/aeat/adapters/outbound/llm/` public exports, internal module layout, error types,
     provider enum, request/response models, and the issue `#20` compatibility
     shim.
  2. Implement the provider adapter contract, the Anthropic adapter, the local
     fallback adapter, and the deterministic `_FakeAdapter`.
- `Phase 2: prompts, cache, usage, translation`
  1. Implement prompt definitions, prompt registry seeds, prompt rendering, and
     request hashing.
  2. Implement `LLMCache`, `UsageRecorder`, `LLMClient`, `Translator`, and
     `BulkTranslator` with retry handling and progress callbacks.
- `Phase 3: settings, CLI, and verification`
  1. Add the LLM settings, `.env.example` entries, and config-alignment tests.
  2. Add the `aeat llm` CLI subtree for complete / translate / cache / usage.
  3. Add colocated unit tests, the opt-in Anthropic live test, and smoke
     coverage for the new subpackage.
  4. Run `just lint`, `just typecheck`, `just test`, and `just hooks`, then
     perform the mandatory code review and fix any findings.

## Parallelization

- External provider research can proceed independently of local repo inspection.
- Implementation should stay mostly sequential because the cache, recorder,
  translator, and CLI all depend on the final request/response and provider
  adapter shapes.
- Code review should run after the implementation and verification pass so it
  audits the final changed-file set once.

## Verification

- `aeat.adapters.outbound.llm` exports the required public API and no external code imports a
  provider SDK directly.
- All boundary types are strict pydantic v2 models and API keys are `SecretStr`.
- Cache hits bypass provider calls and usage files round-trip cleanly.
- `Translator` uses the seeded `translation_v1` prompt and always caches.
- CLI commands are wired into `aeat.entrypoints.cli:app`.
- `just lint && just typecheck && just test && just hooks` pass on Windows.
- Mandatory code review confirms the single-chokepoint rule, strict pydantic
  usage, public API discipline, logging discipline, and green verification.

## Plan Review

- Outcome: approved for execution on `2026-04-12`.
- Review mode: autonomous review recorded per issue instruction requiring the
  full vaultspec pipeline with no human-in-the-loop.
- Checks performed before approval:
  - Confirmed branch boundaries for issues `#10`, `#15`, and `#20`.
  - Confirmed `src/aeat/` package and Typer CLI conventions from the base
    module structure ADR.
  - Confirmed the ADR keeps the implementation inside the issue scope and
    avoids speculative UI or storage work.
