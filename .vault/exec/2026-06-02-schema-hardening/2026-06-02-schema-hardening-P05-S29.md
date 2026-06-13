---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S29'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Split M303 casilla and export pressure fragments

## Scope

- `src/aeat/_data/registry/aeat/modelos/303`

## Description

- Check M303 local diff state before changing registry data.
- Re-measure current M303 line-count and row-size pressure.
- Split both revision casilla fragments at `casillas` table boundaries.
- Split both `0002-export-layout` fragments at export field boundaries.
- Split both `0003-export-layout` fragments at export record boundaries.
- Preserve generic directory-mode semantics without loader or schema changes.
- Compare committed original id order against split-part id order.
- Run focused directory-mode, reviewability, committed-registry, and M303 tests.

## Outcome

- Six M303 pressure files were replaced with twelve ordered `.part-001.toml`
  and `.part-002.toml` fragments.
- The largest M303 registry TOML file is now 898 lines in each `0003` export
  first part.
- No M303 TOML row exceeds 600 characters.
- Parity against `HEAD` preserved both revision casilla id order, `0002`
  export field id order, `0003` export record id order, and `0003` export
  field id order.
- Focused tests passed:
  `test_directory_mode_merges_export_record_field_fragments_by_record_id`,
  `test_committed_registry_toml_files_stay_reviewable`,
  `test_registry_toml_fragments_stay_reviewable`,
  `test_registry_reviewability_baseline_remains_well_below_hard_cap`, all of
  `test_committed_registry.py`, and all of `test_modelo_303_registry.py`.

## Notes

- The first M303 splitter attempt failed at PowerShell parse time due an
  interpolated regex string; no files were changed.
- The second attempt moved originals into `.part-001.toml` and then failed on a
  PowerShell collection issue before writing `.part-002.toml`. The moved
  `.part-001.toml` files still contained the original full content and were
  used as the repair source. The repaired split passed parity checks before
  tests or staging.
