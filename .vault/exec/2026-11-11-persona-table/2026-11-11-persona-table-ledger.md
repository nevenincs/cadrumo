---
tags:
  - '#exec'
  - '#persona-table'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:932fbf0528559c83bbe4c8d5dca146a777a1390e6e40ac2689d0ef8847f6212c'
related:
  - "[[2026-11-11-persona-table-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `persona-table` ledger

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

- `S01` `M` `dev/acceptance/persona_table/rows.py`
- `S01` `M` `dev/acceptance/persona_table/baseline`
- `S01` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S01` `by:` `ACCEPTANCE`
- `S02` `M` `dev/acceptance/persona_table/rows.py`
- `S02` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S02` `by:` `ACCEPTANCE`
- `S03` `M` `dev/acceptance/persona_table/sweep.py`
- `S03` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S03` `by:` `ACCEPTANCE`
- `S04` `M` `dev/fixtures/personas`
- `S04` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S04` `by:` `ACCEPTANCE`
- `S05` `M` `dev/fixtures/personas`
- `S05` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S05` `by:` `ACCEPTANCE`
- `S06` `M` `dev/fixtures/personas`
- `S06` `verify:` `persona table at feature/tui 3049eaae80 (train t3)` -> `pass`
- `S06` `by:` `ACCEPTANCE`

## Notes

- `S01` runner, committed per-row baseline (6f7b81b8e8) and summary separating pass from history-filed, unverified, unsupported, floor-source; t3 195/278
- `S02` 278 rows: every applicable obligation and every history return per persona and supported year from the registry envelope; only sociedad 200 (P02) has no stated values
- `S03` quarters filed locally in chain order before the annual return; Modelo 130 2T-4T 2023-2025 green for all four 130 personas
- `S04` Modelo 130 1T green 2023-2025 for every persona and alta-reciente 2022-2026; the floor year 2022 is floor-source (prior-year Renta below the envelope), carried by S31
- `S05` every Modelo 130 row above the floor year passes with stated, sourced casillas (53 pass)
- `S06` Modelo 111 16/16, 115 16/16, 180 4/4, 190 4/4 green
