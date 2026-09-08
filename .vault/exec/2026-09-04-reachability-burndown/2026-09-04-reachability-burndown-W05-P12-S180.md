---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:9cb9037b6ff8749402e069d72d8c81595ac3fc9e8360fb59930417f0414577e8'
step_id: 'S180'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unreached filed-period selection-reporting slice end to end after proving the canonical capture finalizer does not expose enough evidence to distinguish superseded winners from limited, failed, or unattempted rows, preserving the live finalizer rather than inventing parallel bookkeeping.

## Scope

- `filed-history selection row model and helper`
- `onboarding notice and CLI relay`
- `public operation projection`
- `locale leaves and identity-only tests`
- `focused capture and operation gates`
- `production-metastate and unused-symbol measurements`

## Changes

- `M` `src/cadrumo/application/live/filed_data_capture.py`
- `M` `src/cadrumo/application/live/filed_history_operation.py`
- `M` `src/cadrumo/application/live/tests/test_filed_history_discovery.py`
- `M` `src/cadrumo/application/live/tests/test_filed_history_onboarding.py`
- `M` `src/cadrumo/application/live/tests/test_filed_history_operation.py`
- `M` `src/cadrumo/entrypoints/cli/_app_live.py`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `rg -n "FiledPeriodSelection|filed_period_selection_rows|selection_rows|found_more_than_expected" src/cadrumo -g "*.py"` -> `pass`
- `verify:` `uv run ruff check <S180 Python paths>` -> `pass`
- `verify:` `uv run pytest -q -n0 src/cadrumo/application/live/tests/test_filed_history_discovery.py src/cadrumo/application/live/tests/test_filed_history_onboarding.py` -> `pass` (57 passed)
- `verify:` `uv run --no-sync python -m dev.quality.production_metastate` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.unused_symbol_coverage` -> `fail` (352 exact symbols; 18 orphan test modules)
- `verify:` `uv run --no-sync python -m dev.locales audit` -> `fail` (four peer-owned missing/extra pairs)

- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`

## Notes

The first wiring attempt was withdrawn after review proved captured rows could not distinguish canonical winners from limited, failed, or unattempted rows. The final Step deletes the speculative reporting slice and leaves the canonical latest-per-period finalizer unchanged. Three routed operation tests remain red because the peer-owned observation-envelope validation edit rejects their older fixture; the S180 deletion restores their pre-Step behavior. Locale audit reports only the pre-existing verification-refused and ambiguous-source-disposition drift in all four locales.
