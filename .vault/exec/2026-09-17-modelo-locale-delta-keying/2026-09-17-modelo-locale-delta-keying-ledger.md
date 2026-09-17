---
tags:
  - '#exec'
  - '#modelo-locale-delta-keying'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:e1d4c05a89f457eb2ec22964cf6e336e6da4bbf08d5b2d9b599cee6d98c7cebf'
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
- `S03` `M` `dev/registry/compiler/loader.py`
- `S03` `M` `dev/locales/_registry_scanner.py`
- `S03` `A` `dev/locales/_casilla_keys.py`
- `S03` `M` `dev/locales/manager.py`
- `S03` `M` `dev/locales/_revision_drift.py`
- `S03` `verify:` `pytest dev/locales/tests/test_modelo_revision_locale_key_parity.py test_revision_drift_report.py test_modelo_schema_runtime_localization.py` -> `pass`
- `S04` `A` `dev/locales/modelo_casilla_catalogue.py`
- `S04` `M` `dev/locales/cli.py`
- `S04` `M` `dev/locales/_paths.py`
- `S04` `A` `dev/locales/tests/test_modelo_casilla_catalogue.py`
- `S04` `M` `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `S04` `verify:` `pytest dev/locales/tests/test_modelo_casilla_catalogue.py` -> `pass`
- `S05` `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `S05` `D` `dev/locales/revision_label_restatement.py`
- `S05` `D` `dev/locales/casilla_label_derivation.py`
- `S05` `D` `dev/locales/translation_drift.py`
- `S05` `D` `dev/locales/tests/test_revision_label_restatement.py`
- `S05` `D` `dev/locales/tests/test_casilla_label_derivation.py`
- `S05` `D` `dev/locales/tests/test_translation_drift.py`
- `S05` `M` `dev/quality/metadata/import_load_targets.json`
- `S09` `M` `src/cadrumo/locales`
- `S09` `verify:` `dev.locales casilla-collapse --apply (post-write resolution diffs 0)` -> `pass`
- `S10` `M` `src/cadrumo/locales`
- `S10` `verify:` `dev.locales casilla-audit: derived_help 0, null_leaves 0` -> `pass`
- `S11` `M` `src/cadrumo/locales`
- `S11` `verify:` `dev.locales casilla-author placeholders.json (all changes attributed)` -> `pass`
- `S08` `A` `var/test-iter/wording_review/worklist.json`
- `S08` `by:` `sonnet-worklist`
- `S06` `M` `src/cadrumo/locales/es/modelo/schema`
- `S06` `verify:` `casilla-author spanish_review.json (443 ok, 73 fixed against official designs)` -> `pass`
- `S06` `by:` `sonnet-spanish-review`
- `S07` `M` `src/cadrumo/locales`
- `S07` `M` `dev/locales/tests/test_locale_translation_honesty.py`
- `S07` `A` `dev/locales/tests/test_shipped_casilla_catalogue.py`
- `S07` `verify:` `casilla-audit: stale 0, stranded 0, drift 0, placeholders 0` -> `pass`
- `S12` `M` `dev/locales/modelo_casilla_catalogue.py`
- `S12` `M` `dev/locales/fstring_registry.py`
- `S12` `M` `dev/locales/_signal.py`
- `S12` `M` `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`
- `S12` `M` `dev/locales/tests/test_audit.py`
- `S12` `M` `src/cadrumo/application/modelo/verification_cross_period.py`
- `S12` `M` `src/cadrumo/locales`
- `S12` `verify:` `pytest dev/locales` -> `pass`
- `S12` `A` `dev/locales/casilla_orthography.py`
- `S12` `A` `dev/locales/tests/test_casilla_orthography.py`
- `S12` `M` `dev/locales/cli.py`
- `S12` `M` `src/cadrumo/entrypoints/tui/profile/local_reader.py`
- `S12` `verify:` `pytest dev/locales/tests/test_casilla_orthography.py` -> `pass`
- `S12` `M` `src/cadrumo/domain/calculations/registry/modelo_localization.py`
- `S12` `M` `src/cadrumo/domain/calculations/registry/tests/test_localization_continuity_tier_is_reached.py`
- `S12` `M` `dev/locales/casilla_orthography.py`
- `S12` `verify:` `pytest test_localization_continuity_tier_is_reached` -> `pass`

## Notes

- `S01` barrier changes 19 shipped M303 strings whose Spanish occurrence holds placeholder text; repaired by S11
- `S12` patched rows keep a separate text origin; minimality still judges them (131/2025 carries 8 no-op overrides)
- `S04` first real apply was interrupted by a Windows file lock and re-planned from a partial state, losing 24,861 resolved translations; restored from the verified rehearsal copy, and apply now stages, verifies and installs from a persistent pending directory
- `S07` identical cognates are classified in the honesty allowlist rather than stored as copies
- `S12` Serving no translation where Spanish resolves nowhere removed ~2300 genuine en help texts (ca/hu likewise) that lacked a Spanish source; Spanish help is being authored and the translations restored from 1b7a46e4cb^

