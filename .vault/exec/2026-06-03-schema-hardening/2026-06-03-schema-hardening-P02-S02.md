---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S02'
related:
  - "[[2026-06-03-registry-construct-pressure-plan]]"
---

# Split M200 constructs part 002

## Scope

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records`

## Description

- Confirm the M200 2024-and-later records directory has no local or staged diff
  before editing.
- Split `constructs.part-002.toml` into `constructs.part-002a.toml` and
  `constructs.part-002b.toml`.
- Preserve the same construct id, split the `casillas` array at an item boundary,
  and keep trailing construct member arrays in the second fragment.
- Compare the concatenated split casilla sequence and trailing arrays against the
  committed source.
- Run loader merge, registry reviewability, and committed registry tests.

## Outcome

- `constructs.part-002.toml` was replaced by two lexically ordered same-id
  fragments.
- `constructs.part-002a.toml` has 716 lines and 712 casillas.
- `constructs.part-002b.toml` has 753 lines and 711 casillas plus the original
  trailing construct member arrays.
- The concatenated split preserves all 1,423 casillas in committed source order;
  part A ends at `02798` and part B starts at `02799`.
- The target records directory now tops out at 900-line construct fragments.
- Verification passed:
  `test_directory_mode_merges_construct_member_fragments_by_construct_id`,
  `test_committed_registry_toml_files_stay_reviewable`,
  `test_registry_toml_fragments_stay_reviewable`,
  `test_registry_reviewability_baseline_remains_well_below_hard_cap`, and
  `test_committed_registry.py`.

## Notes

- No loader, schema, validation, inheritance, delta, or modelo-specific behavior
  was added.
- The split was mechanical and did not normalize or edit casilla ids.
