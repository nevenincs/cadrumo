---
tags:
  - '#exec'
  - '#locale-po-informal-register'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:e2356a52ea185b18807605402fb5db745a41d591e8dc0d1ea00e9750bfa055b3'
related:
  - "[[2026-10-02-locale-po-informal-register-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `locale-po-informal-register` ledger

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

- `S01` `M` `src/cadrumo/locales`
- `S01` `M` `dev/locales/tests/test_parity.py`
- `S01` `M` `src/cadrumo/core/i18n/tests/test_hu_error_diacritics.py`
- `S01` `M` `.vaultspec/rules/aeat-locales-cli.md`
- `S01` `A` `.vault/plan/2026-10-02-locale-informal-register-plan.md`
- `S01` `A` `.vault/audit/2026-10-02-locale-informal-register-audit.md`
- `S01` `verify:` `uv run --no-sync python -m scratch_locale_tone.convergence gate` -> `pass`
- `S01` `verify:` `uv run --no-sync pytest -n 0 -p no:randomly -m "unit or integration" <188-test runtime localization selection>` -> `pass`
- `S01` `by:` `root`

## Notes

- `S01` Four corrected Hungarian strings use keys absent from HEAD and remain with concurrent uncommitted TUI caller work; they are excluded from the isolated runtime commit. The original 18-pilot/1371-fleet immutable baselines and accepted official-corpus update receipts remain intact.
