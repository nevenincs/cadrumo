---
tags:
  - '#exec'
  - '#calendar-obligations'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:29daf0a07aa578a8fafd194f8226e3853089a577e9bcd1bcb545b7e3bea97870'
related:
  - "[[2026-09-23-calendar-obligations-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `calendar-obligations` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S01` `M` `src/cadrumo/_data/registry/aeat/facts/0143-deadline-calendar-territory-catalogue.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/legal/ley-39-2015-notificaciones.toml`
- `S01` `M` `src/cadrumo/domain/calculations/registry/calendar_ccaa_catalogue.py`
- `S01` `A` `src/cadrumo/domain/calculations/registry/tests/test_calendar_ccaa_catalogue.py`
- `S01` `verify:` `ruff check, ruff format, ty, basedpyright, pyrefly on changed files` -> `pass`
- `S02` `M` `src/cadrumo/domain/deadlines/festivos.py`
- `S02` `M` `src/cadrumo/domain/deadlines/models.py`
- `S02` `M` `src/cadrumo/domain/deadlines/profiles.py`
- `S02` `M` `src/cadrumo/domain/deadlines/tests/test_festivos.py`
- `S02` `M` `src/cadrumo/application/overview/calendar.py`
- `S02` `M` `src/cadrumo/application/overview/calendar_models.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_calendar.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_home.py`
- `S02` `M` `src/cadrumo/application/overview/tests/test_calendar_filing_evidence.py`
- `S02` `M` `src/cadrumo/application/modelo/tests/test_declarations_calendar.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_overview.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_overview_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/_overview_rendering.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_overview_calendar_verb.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/tests/workbench_fixtures.py`
- `S02` `M` `src/cadrumo/locales/en/application.yml`
- `S02` `M` `src/cadrumo/locales/es/application.yml`
- `S02` `M` `src/cadrumo/locales/ca/application.yml`
- `S02` `M` `src/cadrumo/locales/hu/application.yml`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `A` `src/cadrumo/domain/deadlines/tests/test_holiday_territory_profile.py`
- `S02` `verify:` `ruff, format, ty, basedpyright, pyrefly on changed files` -> `pass`

## Notes

- `S01` published logical_generation 5159b729af5353be4a71983c93a68ad73ad86f39d37578fc70e643257e49e9be
- `S02` S02 also carries the CLI projection and the cli-to-application shift-label key move; the TUI projection is S03

