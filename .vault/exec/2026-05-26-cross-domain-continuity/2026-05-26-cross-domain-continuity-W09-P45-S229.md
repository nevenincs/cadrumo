---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:9283d9dc6678dbe758e73cf9432e309fd19532a91f5f0454839817e7239c187c'
step_id: 'S229'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-INES-3 register --output-language option on overview calendar to parity-match other commands

## Scope

- `currently rejected with No such option --output-language`
- `src/aeat/entrypoints/cli/_overview.py`

## Description

- Ground the parity gap with plan and code RAG searches before editing.
- Verify the established CLI pattern: import `OutputLanguage` from `aeat.core.external_constants` and call `activate_subcommand_output_language` from the CLI common module.
- Register `--output-language` and `--language` on `aeat app overview calendar`.
- Activate the requested output language at the start of the calendar verb before date parsing, active-profile checks, all-profile dispatch, and refusal rendering.
- Add real CLI regression coverage proving help advertises the supported language choices and Catalan refusal text renders after `--output-language ca`.

## Outcome

Closed. `aeat app overview calendar --help` now lists `--output-language,--language [es|en|ca|hu]`, and the calendar verb accepts the option instead of failing with `No such option`. Refusal rendering now honours the subcommand language override before the calendar body emits validation errors.

## Notes

- Validation: `uvx vaultspec-rag search "W09.P45.S229 R7-INES-3 register --output-language overview calendar parity No such option" --doc-type plan --port 8766 --timeout 30` surfaced the open S229 plan row.
- Validation: `uvx vaultspec-rag search "overview calendar output-language option language profile active locale CLI" --type code --port 8766 --timeout 30` surfaced the output-language option pattern and overview calendar owner.
- Validation: `uv run --no-sync ruff check src\aeat\entrypoints\cli\_overview.py src\aeat\entrypoints\cli\tests\test_overview_calendar_verb.py` passed.
- Validation: `uv run --no-sync pytest -q -m "integration and hex_entrypoint" src\aeat\entrypoints\cli\tests\test_overview_calendar_verb.py::test_calendar_help_advertises_local_only src\aeat\entrypoints\cli\tests\test_overview_calendar_verb.py::test_calendar_output_language_applies_before_refusal_rendering` passed with two tests.
- Validation: `uv run --no-sync aeat app overview calendar --help` showed `--output-language,--language [es|en|ca|hu]`.
- Validation: an isolated direct smoke of `uv run --no-sync aeat app overview calendar --output-language ca --from not-a-date --to 2026-03-31` exited nonzero with Catalan `Format de data invàlid` and without `No such option`.
- Note: a first direct smoke without `AEAT_SECRET_PASSPHRASE` hit the expected non-interactive passphrase guard before command validation; the isolated rerun supplied the dev/test passphrase and temp storage root.
- Note: unrelated peer WIP was present in `src/aeat/application/overview/_calendar.py` and `src/aeat/application/overview/tests/test_calendar.py`; neither file was edited.
