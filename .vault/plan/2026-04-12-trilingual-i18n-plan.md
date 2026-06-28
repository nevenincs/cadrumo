---
tags:
  - "#plan"
  - "#trilingual-i18n"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-trilingual-i18n-research]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
---

# Trilingual i18n implementation plan

This plan details the implementation of Issue #20 (Trilingual i18n) based on the architectural decisions established in the trilingual-i18n ADR.

## Proposed Changes

We will introduce a new `aeat.core.i18n` subpackage to handle our trilingual contract (Spanish, English, Hungarian). Instead of gettext or `.po` files, we will use a Nested-dict shape (`Translatable` TypedDict) and a `Language` Enum, with Spanish as the authoritative language for domain data. We will also update our global configuration to support setting the output language via an environment variable (`AEAT_OUTPUT_LANGUAGE`), and ensure all implementation adheres strictly to the project's testing and type-hinting standards.

## Tasks

- Phase 1
  1. Scaffold i18n package and configuration
     - Name: Scaffold src/aeat/core/i18n/ and config
     - Step summary: `.vault/exec/2026-04-12-trilingual-i18n/2026-04-12-trilingual-i18n-phase1-step1.md`
     - Executing agent: vaultspec-standard-executor
     - References: `2026-04-12-trilingual-i18n-adr`
     - Details: Create `src/aeat/core/i18n/__init__.py`. Update `src/aeat/config.py` to add `aeat_output_language` (mapping to `AEAT_OUTPUT_LANGUAGE`). Update `env/.env.example` and `tests/test_config.py` to ensure alignment.
  2. Implement core i18n primitives
     - Name: Implement Language, Translatable, and helper functions
     - Step summary: `.vault/exec/2026-04-12-trilingual-i18n/2026-04-12-trilingual-i18n-phase1-step2.md`
     - Executing agent: vaultspec-high-executor
     - References: `2026-04-12-trilingual-i18n-adr`
     - Details: In `src/aeat/core/i18n/`, implement `Language` Enum (es, en, hu), `Translatable` TypedDict (nested-dict shape), `TranslationFallback` policy, and helper functions `get_translation`, `require_authoritative`, and `with_translation`. Add Google-style docstrings and full type hints. Use `AeatError` for any domain errors. NO gettext or .po files.
  3. Add unit tests for i18n primitives
     - Name: Add unit tests for i18n primitives
     - Step summary: `.vault/exec/2026-04-12-trilingual-i18n/2026-04-12-trilingual-i18n-phase1-step3.md`
     - Executing agent: vaultspec-standard-executor
     - References: `2026-04-12-trilingual-i18n-adr`
     - Details: Create `src/aeat/core/i18n/test_i18n.py` (or `test_smoke.py`). Add comprehensive unit tests for all primitives. No mocks, patches, fakes, or stubs allowed.
  4. Document the trilingual contract
     - Name: Update CLAUDE.md with trilingual contract
     - Step summary: `.vault/exec/2026-04-12-trilingual-i18n/2026-04-12-trilingual-i18n-phase1-step4.md`
     - Executing agent: vaultspec-documentation
     - References: `2026-04-12-trilingual-i18n-adr`
     - Details: Update `CLAUDE.md` to document the trilingual contract (es=authoritative for AEAT, en=authoritative for code/docs, hu=user-facing output). Detail the usage of Nested-dict shape instead of gettext.

## Parallelization

Tasks 1 and 4 can be parallelized. Task 2 must follow Task 1. Task 3 must follow Task 2.

## Verification

Run all unit tests to ensure `Language`, `Translatable`, and helper functions work exactly as specified without any mocking. Verify `test_config.py` passes to confirm `config.py` and `.env.example` remain aligned. Check `CLAUDE.md` to ensure the contract is clearly documented. Ensure type-checking passes.

## EXPLICIT PLAN REVIEW

- **Issue Scope Checks**: The plan strictly follows the requirements: scaffolds the package, updates `config.py` and `test_config.py`, implements exactly the required primitives (`Language`, `Translatable`, `TranslationFallback`, `get_translation`, `require_authoritative`, `with_translation`), adds collocated unit tests, updates `CLAUDE.md`. It explicitly forbids mocks/patches/fakes/stubs, and forbids gettext/.po files. It mandates Google-style docstrings, type hints, and `AeatError` inheritance.
- **Vaultspec Checks**: The plan follows the standard Vaultspec plan structure. Frontmatter uses strictly `["#plan", "#trilingual-i18n"]`, and `related:` contains `[`2026-04-12-trilingual-i18n-adr`]`. Steps use the required Executing agent format.
- **Review Outcome**: Plan is APPROVED.
