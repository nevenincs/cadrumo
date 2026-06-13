---
tags:
  - "#plan"
  - "#multilang-externalization"
date: 2026-05-04
modified: '2026-05-04'
related:
  - "[[2026-05-04-multilang-externalization-phase1-adr]]"
  - "[[2026-05-04-multilang-externalization-phase1-research]]"
---

# Multilang Externalization Phase 1 Plan

## Goal
Build out a centralized localization backend using `python-i18n` and execute an aggressive, exhaustive teardown of all previous multilang attempts. Ensure absolutely no compatibility remnants, language hints, or old testing structures remain in the codebase.

## Execution Meta-Stages

### Stage 1: Buildout of Centralized Localization Backend
1. **Dependencies:** Add `python-i18n` and `PyYAML` to `pyproject.toml` (Completed).
2. **Scaffolding:** Provision `src/aeat/locales/*.yml` for `es`, `en`, `ca`, and `hu` (Completed).
3. **Backend Initialization:** Rip out the contents of `src/aeat/entrypoints/cli/_i18n.py` and replace it with a pure `python-i18n` initialization and wrapper. Do not leave a deprecated `t(...)` wrapper.

### Stage 2: Aggressive Pruning & Teardown (No Compatibility)
1. **Core Deletion:** Delete `src/aeat/core/i18n/test_i18n.py`, `src/aeat/core/i18n/test_diacritic_consistency.py`, and the entire `src/aeat/core/i18n/` module if it only contains the old primitives.
2. **Remove Language Hints:** Delete all `Language` enums, `Translatable` types, and `TranslationError` definitions.

### Stage 3: Extensive Line-by-Line / Class-by-Class Audit
1. **Core Domains Audit:** The teardown must extend beyond the CLI. Explicitly scour and centralize:
   - **Errors and Exceptions:** Standardize all raised exceptions and error messages.
   - **Status Messages:** Centralize all status reporting output.
   - **UX Corpus:** Centralize all user-facing documentation, prompts, and interface strings.
2. **CLI Audit:** Scour every file in `src/aeat/entrypoints/cli/` (e.g., `auth`, `bootstrap`, `cloud`, `docs`, `doctor`, `drive`, `financial`).
3. **Surgical Extraction:** For every `tr(t(es=..., en=..., ca=..., hu=...))` occurrence, rip it out entirely.
4. **Key Replacement:** Replace the ripped-out structure with a clean `tr("namespace.key")` abstract key call.
5. **YAML Population:** Populate the corresponding extracted strings into the YAML files in a structured manner.
6. **Class/Module Audit:** Search the broader `src/aeat/` tree for any other classes or functions attempting to implement `multilang` kwargs or `en=`, `es=` parameters and strip them down to use the centralized backend.

### Stage 4: Manual Remediation and Verification
The automated subagent pass left syntax and type errors. As per steering, we will manually edit the files, avoiding programmatic scripts.
1. **Auth & Catalogue Domain:**
   - [ ] `src/aeat/application/auth/_catalogue.py`
   - [ ] `src/aeat/application/auth/test_catalogue.py`
   - [ ] `src/aeat/entrypoints/cli/auth/_render.py`
   - [ ] `src/aeat/entrypoints/cli/auth/test_auth_cli.py`
2. **Filing Domain:**
   - [ ] `src/aeat/application/filing/_calculate.py`
   - [ ] `src/aeat/application/filing/test_calculate.py`
   - [ ] `src/aeat/application/filing/_export.py`
   - [ ] `src/aeat/application/filing/test_export.py`
   - [ ] `src/aeat/application/filing/test_filing.py`
   - [ ] `src/aeat/application/filing/reconciliation/test_reconcile.py`
   - [ ] `src/aeat/domain/filing/_validator.py`
3. **Core & Errors Domain:**
   - [ ] `src/aeat/core/access_gate/_errors.py`
   - [ ] `src/aeat/core/errors/__init__.py`
   - [ ] `src/aeat/core/errors/_registry.py`
   - [ ] `src/aeat/application/aggregation/_errors.py`
   - [ ] `src/aeat/application/review/_adapters.py`
4. **Categories & Profile Domain:**
   - [ ] `src/aeat/domain/categories/_profile.py`
   - [ ] `src/aeat/domain/categories/_registry.py`
   - [ ] `src/aeat/domain/categories/test_profile.py`
   - [ ] `src/aeat/domain/profile/_errors.py`
   - [ ] `src/aeat/domain/profile/_keys.py`
   - [ ] `src/aeat/domain/profile/test_keys.py`
5. **Other Domains:**
   - [ ] `src/aeat/domain/manuals/_loader.py`
   - [ ] `src/aeat/domain/manuals/_verify.py`
   - [ ] `src/aeat/domain/manuals/test_schema.py`
   - [ ] `src/aeat/domain/normatives/test_schema.py`
   - [ ] `src/aeat/domain/portals/_metadata.py`
   - [ ] `src/aeat/domain/vat/test_rules.py`
   - [ ] `src/aeat/entrypoints/cli/registry.py`
   - [ ] `src/aeat/entrypoints/cli/test_no_hardcoded_user_strings.py`

6. **Final Verification:**
   - Run `just typecheck`, `just lint`, and `just test` to ensure zero regressions.
