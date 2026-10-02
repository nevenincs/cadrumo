---
tags:
  - '#exec'
  - '#modelo-filing-ux-followup'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:d845a587755b2c087b74c6d6f8d1f7cf3944a7cb8317d4928a78b51c88250b33'
related:
  - "[[2026-10-02-modelo-filing-ux-followup-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `modelo-filing-ux-followup` ledger

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

- `S01` `M` `src/cadrumo/application/modelo/declarations_list.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_declarations_list.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/grouped.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/row_words.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/picker.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_new_declaration_picker.py`
- `S01` `M` `src/cadrumo/entrypoints/tui/declarations/tests/test_row_words.py`
- `S01` `A` `src/cadrumo/entrypoints/tui/declarations/tests/test_declarations_guidance.py`
- `S01` `M` `src/cadrumo/locales/es/common.yml`
- `S01` `M` `src/cadrumo/locales/en/common.yml`
- `S01` `M` `src/cadrumo/locales/ca/common.yml`
- `S01` `M` `src/cadrumo/locales/hu/common.yml`
- `S01` `verify:` `focused live declaration units (39)` -> `pass`
- `S01` `verify:` `real keyboard guidance and picker integrations (33)` -> `pass`
- `S01` `verify:` `calendar external completion and declarations projection units (32)` -> `pass`
- `S01` `verify:` `installed encrypted creation and external details integrations (17)` -> `pass`
- `S01` `verify:` `Ruff format check all eight Python paths` -> `pass`
- `S01` `verify:` `Ruff check all eight Python paths` -> `pass`
- `S01` `verify:` `configured ty check all eight Python paths` -> `pass`
- `S01` `verify:` `exact twelve after hashes match reviewed5b7d candidate` -> `pass`
- `S01` `verify:` `vault plan check` -> `pass`
- `S01` `M` `dev/locales/fstring_registry.py`
- `S01` `M` `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`
- `S01` `verify:` `s01-locale-discovery 30 cases` -> `pass`
- `S01` `verify:` `s01-caption-ui 16 integrations` -> `pass`
- `S01` `verify:` `s01-caption format lint configured-ty` -> `pass`
- `S01` `verify:` `s02-locale-inventory introduced four missing cells` -> `fail`
- `S01` `verify:` `s01-locale-inventory-repaired required missing0` -> `pass`
- `S01` `verify:` `s04-native-frozen16 declarations stable and principal accepted` -> `pass`
- `S02` `M` `src/cadrumo/locales/es/common.yml`
- `S02` `M` `src/cadrumo/locales/en/common.yml`
- `S02` `M` `src/cadrumo/locales/ca/common.yml`
- `S02` `M` `src/cadrumo/locales/hu/common.yml`
- `S02` `M` `docs/how-to/fill-in-and-file-in-the-workbench.md`
- `S02` `M` `docs/locales/es/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po`
- `S02` `M` `docs/locales/ca/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po`
- `S02` `M` `docs/locales/hu/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po`
- `S02` `verify:` `s02-scoped catalogue parity placeholders character/cell caps` -> `pass`
- `S02` `verify:` `s02-help-contract 24 tests` -> `pass`
- `S02` `verify:` `s04-docs-completeness 10 authored units` -> `pass`
- `S02` `verify:` `s04-docs-full-strict-en full build` -> `pass`
- `S02` `verify:` `s05-docs-frozen-authority-es full strict build` -> `pass`
- `S02` `verify:` `s05-docs-frozen-authority-ca full strict build` -> `pass`
- `S02` `verify:` `s05-docs-frozen-authority-hu full strict build` -> `pass`
- `S02` `by:` `vaultspec-high-executor`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/screen.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/casilla_list.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_help_and_footer.py`
- `S03` `M` `src/cadrumo/entrypoints/tui/modelo/workbench/tests/test_workbench_records_real.py`
- `S03` `M` `docs/how-to/fill-in-and-file-in-the-workbench.md`
- `S03` `M` `docs/locales/es/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po`
- `S03` `M` `docs/locales/ca/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po`
- `S03` `M` `docs/locales/hu/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po`
- `S03` `verify:` `s03-footer-unit-corrected 50 tests` -> `pass`
- `S03` `verify:` `s03-record-installed 37 tests` -> `pass`
- `S03` `verify:` `s03 configured format lint types` -> `pass`
- `S03` `verify:` `principal frozen-native record20 footer review` -> `pass`
- `S03` `verify:` `two-paragraph scoped PO completeness and strict frozen locale builds` -> `pass`
- `S03` `by:` `vaultspec-high-executor`

## Notes

- `S01` Initial exact5b7d twelve-path integration committed3d40; later total typed caption map repairs obsolete discovery registration without duplicate state key. Full repaired census remains failing for baseline19 inventory plus in-progress docs4 and spelling tool; no aggregate-green claim. Receipt work/UX5-checks/s01-locale-inventory-delta.json separates the introduced four missing cells and their repair. Final native source receipt excludes unrelated auth/profile writes; calendar proof remains owning typed projection.
- `S02` Live localized strict builds refused unrelated auth config.logout sequences; corrected frozen admitted-source builds pass. Native Hungarian human review remains release-pending. Foreign live informal-register overlap on two HU leaves is preserved and excluded from this Step's staged leaf delta; frozen accepted copy is evidence-versioned.
- `S03` The initial scratch footer run was repaired to preserve fieldless Help plus actual named Next, worded Scroll and Back within 80 columns. Later narrow header findings belong S05; original footer captures are applicability evidence for this bounded action surface.
