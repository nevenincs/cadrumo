---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:d0c8fdf69632a02ebe14b13f9e9d2dd9a9bd38f5f70181ca8fef4012d478c5f6'
step_id: 'S128'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Delete the locale identical-translation disposition ledger and its allow-identical mutation path, treating linguistic equality as content rather than development state while retaining structural zero-target checks

## Scope

- `locale manager`
- `status reporting`
- `CLI`
- `tests`
- `and shipped locale metadata`

## Changes

- `M` `dev/locales/_ast_scanner.py`
- `M` `dev/locales/_status.py`
- `M` `dev/locales/cli.py`
- `M` `dev/locales/manager.py`
- `D` `dev/locales/tests/test_allow_identical.py`
- `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `M` `dev/locales/tests/test_scaffold_admits_no_unvalued_key.py`
- `M` `dev/locales/tests/test_status.py`
- `M` `dev/tests/test_text_writer_newline_pinning.py`
- `M` `src/cadrumo/application/user_profile/tests/test_overview_localization.py`
- `D` `src/cadrumo/locales/_intentional_identical.json`
- `verify:` `uv run --no-sync pytest -q dev/locales/tests/test_status.py dev/locales/tests/test_locale_translation_honesty.py dev/locales/tests/test_scaffold_admits_no_unvalued_key.py src/cadrumo/application/user_profile/tests/test_overview_localization.py` -> `pass`
- `verify:` `uv run --no-sync ruff check ...` -> `pass`

## Notes

The text-writer gate still reports four peer-owned unpinned writers and 21 tracked-but-deleted stale inputs; removal of the obsolete locale exemption introduced no additional finding.
