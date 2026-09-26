---
tags:
  - '#reference'
  - '#assets-core'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:c45368419091a7a6881337cbab2e6fadcac6b0f122d212cca1a9ca9eec2cd51f'
related:
  - "[[2026-09-23-assets-core-plan]]"
---

# `assets-core` reference: `How indexed profile objects are written and read today`

Schema version 7 declares `irpf.plantilla_media` as an indexed object on the
non-repeatable `irpf` section (`src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml:1312-1319`),
with its validators and reader in `src/cadrumo/domain/user_profile/plantilla_media.py`
and the write-time hook `_plantilla_media_issues`
(`src/cadrumo/application/user_profile/validation.py:543-559`). Nothing can
write it: `config profile add-row` reaches repeatable sections only.

## Patterns

### The descendant subject rewrites a compacted set

`config profile descendiente` (`src/cadrumo/entrypoints/cli/config/profile_command_specs.py:478-498`,
`:847-892`) loads the record, rebuilds every `renta_family.descendiente.*` path
at indices 0..n-1 and clears stale paths
(`src/cadrumo/entrypoints/cli/config/descendiente.py:61-116`). Removing one row
renumbers the rest, and load and write read the record separately with no
`expected_record`.

### Stable indices exist for repeatable sections

`next_section_row_index` allocates max plus one and counts cleared indices as
occupied, and `remove_profile_repeatable_section_row` clears a row with
`value=None` (`src/cadrumo/application/user_profile/section_rows.py:128-162`,
`:312-348`).

### One write door with compare-and-swap

`apply_profile_fact_changes(profile_id, changes, door, expected_record,
profile_decode_context)` merges by path, runs the validation hooks and writes
through a compare-and-swap; blocking issues raise `ProfileSchemaValidationError`
(`REFUSED_PROFILE_SCHEMA_VALIDATION`) (`src/cadrumo/application/user_profile/fact_write.py:53-129`).
Each caller names a `ProfileFactWriteDoor` member, enrolled in
`src/cadrumo/application/user_profile/tests/test_fact_write_door_contract.py:40-50`.
The fact value validator turns `"2024"` and `"12.50"` into `Decimal`
(`src/cadrumo/domain/user_profile/values.py:161-204`).

### The TUI cannot add or remove an object instance

`ProfileManagerScreen` edits one existing leaf at a time and offers Add only for
repeatable sections (`src/cadrumo/application/user_profile/overview.py:778-795`,
`:1009-1084`); no screen edits descendants or other indexed objects.

### Reads through the profile port are strings

`ProfilePathValuesReadPort` returns `record_to_path_values`, a
`Mapping[str, str]` (`src/cadrumo/application/user_profile/profile_read_ports.py:16-35`,
`src/cadrumo/application/user_profile/projections.py:204-218`), while
`plantilla_media_years` refuses a string year or workforce
(`src/cadrumo/domain/user_profile/plantilla_media.py:74-102`), so any consumer
reading through the port is refused for every declared year. The activity-asset
operations read the taxpayer modality through the same port at
`src/cadrumo/entrypoints/cli/_actividad_asset_cli.py:114-119` and
`src/cadrumo/entrypoints/tui/launcher.py:818-824`.

### What a new CLI subject touches

Command specs and the handler map, a payload module enrolled in
`src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py:68-105`,
four `cli.yml` catalogues, the cold-leaf lists in
`src/cadrumo/entrypoints/cli/tests/test_machine_secret_channels_subprocess.py:732-799`,
and the regenerated `dev/quality/metadata/import_load_targets.json` and
`application_entrypoint_modules.json`. `_leaf` turns a `plantilla_media` parent
into a `plantilla.media` identity (`profile_command_specs.py:208-211`); the CLI
reference is generated at docs build time and not committed.
