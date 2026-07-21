---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S328'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ZSOFIA-A localise weekday shift enum values in overview calendar output

## Scope

- `today raw Spanish sabado/domingo leaks into operator-facing shift= field`
- `render via tr() with locale-mapped day names`
- `src/aeat/application/overview/`

## Description

- Ground the defect with `vaultspec-rag` and trace overview calendar text output to the `shift=` field renderer.
- Replace hardcoded shift-language mappings with literal `tr()` calls for scaffold-visible locale keys.
- Preserve raw `shift_reason` values in JSON payloads while localizing text-mode `shift=` labels.
- Add locale leaves for English, Spanish, Catalan, and Hungarian through the locale CLI.
- Strengthen focused calendar tests so text output localizes labels and JSON keeps tokens.

## Outcome

- Text calendar rows now render localized shift labels such as `Business day`, `Dissabte`, and `Diumenge` instead of raw `business_day`, `sabado`, or `domingo` tokens.
- JSON calendar payloads continue to expose raw `shift_reason` tokens for machine consumers.
- Locale scaffold and audit both pass for `en`, `es`, `ca`, and `hu`.

## Notes

- Validation: `uv run --no-sync ruff check src/aeat/entrypoints/cli/_overview.py src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py`; `uv run --no-sync pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_text_localizes_shift_label_but_json_keeps_token src/aeat/entrypoints/cli/tests/test_overview_calendar_verb.py::test_calendar_shift_formatter_localizes_weekend_tokens -q`; `uv run --no-sync python -m aeat.locales scaffold --check`; `uv run --no-sync python -m aeat.locales audit`.
- Locale files were updated through `aeat.locales scaffold` and `aeat.locales set`; nearby YAML scalar wrapping changed as CLI-owned serialization churn.
