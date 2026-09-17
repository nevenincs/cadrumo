---
tags:
  - '#exec'
  - '#modelo-locale-delta-keying'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:f3f11a5520d3a757fa1fe8fa694ba37fde9af7c7c342393391ce6ae0aaad1610'
related:
  - "[[2026-09-17-modelo-locale-delta-keying-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `modelo-locale-delta-keying` ledger

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
- `S01` `M` `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/tests/test_localization_continuity_tier_is_reached.py`
- `S01` `M` `dev/registry/tests/test_isolated_edition_staging.py`
- `S01` `verify:` `pytest test_localization_continuity_tier_is_reached test_isolated_edition_staging` -> `pass`
- `S02` `M` `src/cadrumo/domain/calculations/registry/static_inspection.py`
- `S02` `M` `src/cadrumo/application/modelo/workspace.py`
- `S02` `verify:` `pytest test_workspace test_workspace_models` -> `pass`
- `S12` `M` `dev/registry/compiler/loader_materialisation.py`
- `S12` `verify:` `pytest test_delta_minimality test_edition_delta_migration test_revision_label_inheritance test_isolated_edition_staging` -> `pass`

## Notes

- `S01` barrier changes 19 shipped M303 strings whose Spanish occurrence holds placeholder text; repaired by S11
- `S12` patched rows keep a separate text origin; minimality still judges them (131/2025 carries 8 no-op overrides)

