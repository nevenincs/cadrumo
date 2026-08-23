---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:2e0c1ef9cdcdc349b1043204607306db8f3fadef8284f14f3e4792898801dbd6'
step_id: 'S23'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---
# Reconcile post-close user-documentation catalogue drift across Spanish, Catalan, and Hungarian by synchronizing the seven source-divergent pages, translating every incomplete entry across the current thirty-page backlog, and proving the full completeness and fresh-POT equality gates return zero without excluding a page or accepting fuzzy fallback

## Scope

- `docs/locales/{es,ca,hu}/LC_MESSAGES; dev/docs/tests/test_docs_localization.py; dev/docs/tests/test_docs_catalogue_drift.py`

## Description

- Re-extract the current 57-page user-documentation POT set through the canonical docs i18n pipeline.
- Synchronize the seven source-divergent catalogues in all three target languages.
- Translate every untranslated or fuzzy entry in the current thirty-page completeness backlog with page context and preserved code, JSON, command, and link literals.
- Run the complete per-language completeness and fresh-POT msgid-equality gates without exclusions or fuzzy fallback.

## Outcome

Open carry-forward. On 2026-08-23 the completeness gate completed with three failures, one per language. Each language has the same 30 of 57 pages incomplete; the reviewed `how-to/protect-data-access.md` catalogue is absent from all three inventories and independently reports zero untranslated, fuzzy, or obsolete entries.

The fresh-POT drift gate also completed with three failures, one per language, each naming the same seven pages: `download.md`, `how-to/classify-transactions.md`, `how-to/index.md`, `index.md`, `reference/commands-and-configuration.md`, `reference/identity-and-naming.md`, and `workstation-setup.md`. The reviewed protect-data-access page is absent from this inventory as well.

This is post-close drift in the user-documentation localization campaign, not a remaining machine-secret translation defect. The machine-secret S18 review therefore preserves the full standing criteria by delegating this exact finite backlog here rather than declaring the broad lane green or absorbing thirty unrelated pages.

## Notes

Closure requires both commands to collect and pass all three language cases on one coherent HEAD: `uv run --no-sync pytest -q -n 0 dev/docs/tests/test_docs_localization.py::test_every_user_page_is_fully_translated` and `uv run --no-sync pytest -q -n 0 -m integration dev/docs/tests/test_docs_catalogue_drift.py::test_catalogue_msgids_match_current_source`. The result must contain no page exclusion, incomplete or fuzzy msgstr, stale catalogue msgid, or source msgid absent from a catalogue.
