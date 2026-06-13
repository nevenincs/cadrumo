---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S275-001 | PASS | Prompter storage ownership

The `W12.P26.S275` review found that `src/aeat/application/wizard/_prompter.py`
does not own persistence. The module renders questionary prompts, returns
canonical-token strings, and logs progress through the structured logger. It does not
construct repositories, write bucket manifests, manage master-key material, read
environment variables, or open plaintext side files.

## S275-002 | PASS | Plaintext exception hardening

Interactive unsupported-console paths already raise `WizardUnsupportedConsoleError`
with `translated_message="wizard.errors.unsupported_console"` and preserve the
prompt-toolkit exception as the cause for diagnostics. The scripted prompter underflow
and overflow paths now also raise AEAT wizard exceptions with locale keys and bounded
structured context instead of raw English exception messages.

Follow-up review corrected the overflow path to avoid placing raw unconsumed scripted
answers in exception context. The overflow context now reports counts only, so fixture
drift remains debuggable without exposing canonical-token values that may carry
operator input.

## S275-003 | PASS | PATH prompt boundary

The PATH widget dispatches to `questionary.path` and returns `_stringify(result)`.
It does not resolve, expand, validate, read, or write the returned path. Downstream
canonicalization and persistence remain outside this prompter boundary.

## S275-004 | PASS | Duplication and validation

Vaultspec RAG semantic search clustered the slice with wizard prompter errors,
questionary smoke tests, locale registry keys, and wizard command orchestration. The
change reuses the existing registered locale keys for wizard scripted fixture drift
instead of adding duplicate message vocabulary.

The prompter overflow test is a real behavior test against the production
`ScriptedPrompter` and production `WizardScriptOverflowError`. It does not use mocks,
fakes, monkeypatching, skips, or duplicated business logic.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_prompter.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync -q python -m aeat.locales audit`

Disposition: close `AFR-173`.
