---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:735013394b69efc3ae9d9f5b5b376e5411594cc0dd55146961e4f04ae982befc'
step_id: 'S05'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# add the dry-run short-circuit and flag to the Sheets export, reporting the ranges it would clear and the cells that would change

## Scope

- `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`
- `src/cadrumo/entrypoints/cli/_config/_google_payloads.py`
- `src/cadrumo/adapters/outbound/google/_calc_sheets_apply.py`
- `src/cadrumo/adapters/outbound/google/_calc_sheets_apply_values.py`
- `src/cadrumo/adapters/outbound/google/__init__.py`

## Description

SCOPE CORRECTION carried over from the sibling `P02.S04` record rather than
rediscovered. That record already established that the ranges-to-clear and
cell-change halves cannot live in the CLI layer: the stale-clear set has to be
derived from the exact payload the write would send, and re-deriving it from
the plan a second time in the CLI would reintroduce the drift risk the
write-then-clear ordering fix (`P01.S02`) exists to prevent. Both halves
therefore live in the adapter, immediately before the point a real apply would
issue its write calls, and the CLI only threads the flag through and renders
the result.

Built as a genuinely read-only preview rather than a write with a skipped
final call:

- `preview_export_plan` resolves the SAME `cadrumo-vault/calc-sheets/{modelo}-{period}-{year}/`
  target `apply_export_plan` resolves, through the SAME read-only lookup
  (`_find_folder` / `_find_spreadsheet`) rather than the create path
  (`_ensure_folder` / `_create_spreadsheet`), so a preview cannot describe a
  different target than a real apply would.
- A target with nothing on Drive to look up yet previews via
  `_new_target_export_preview`: every value cell reads as new content and
  there is nothing to clear, because creating the target to answer the
  question would be exactly the write a preview exists to avoid.
- When the target exists, the preview reads the current occupied cell VALUES
  (not merely presence) through a new `_current_cell_values` family, added
  alongside the existing presence-only `_occupied_addresses` family rather
  than replacing it — the two now share one response-walking core so they
  cannot drift on what counts as occupied.
- `written_cell_values` is `payload_written_addresses`'s value-carrying
  sibling, both derived from one shared walk (`_walk_payload_entries`) so the
  address set and the value map cannot disagree.
- `changed_cell_addresses` compares the two through
  `core.decimal.coerce_decimal` normalisation on both sides, so a Decimal
  written as fixed-point text (`"1234.50"`) is compared against the number
  Sheets already stores (`1234.5`) rather than failing every numeric cell on
  string shape alone.
- Formula cells are reported as an unconditional `formula_cells_to_write`
  count, never diffed value-for-value: a real apply always rewrites every
  formula cell it carries regardless of whether its computed result would
  differ, so a preview that tried to diff formula TEXT against a currently
  computed VALUE would compare two different kinds of thing and answer a
  question the real write does not ask either.
- `GoogleSyncCalcExportResult` carries the preview fields as defaultable
  additions (`dry_run`, `spreadsheet_exists`, nullable `folder_id` /
  `spreadsheet_id` / `spreadsheet_url`, `ranges_to_clear`,
  `value_cells_changed`, `value_cells_unchanged`, `formula_cells_to_write`)
  on the SAME registered schema rather than a second one — a second schema
  cannot register under the same `config.google.sync.calc.export` command
  path, and `FiledCaptureResult` already established the one-schema,
  `dry_run`-branched shape for this exact contract.

## Outcome

`--dry-run` is a real flag on `aeat config google sync calc export`,
localised in all four catalogues. `dry_run` rides the envelope's `result`
payload as primary data, never the `notices` channel, matching the binding
constraint and the filed-sweep precedent.

Twelve offline tests in
`src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_export_preview.py`
prove the diff machinery against a REAL modelo-130 plan (never a synthetic
payload alone): `written_cell_values` and `payload_written_addresses` cannot
drift (same address set, same walk); `changed_cell_addresses` correctly
matches Decimal-vs-numeric-text, treats an unread address as matching only a
blank target, and never coerces a boolean through Decimal; a target with
nothing on Drive previews as fully new; and a structural proof
(`ast`-stripped of its own docstring, so the assertion cannot pass on prose
alone) confirms `preview_export_plan`'s source never names a write-capable
helper (`_create_folder`, `_ensure_folder`, `_create_spreadsheet`,
`_ensure_plan_tabs_and_grid`, `_force_spreadsheet_locale`,
`_write_plan_values`, `_clear_stale_addresses`,
`_apply_plan_structural_requests`) or a write-shaped Sheets/Drive action
label, and only ever calls the two read-only lookups.

## Notes

Ran locally: `pytest src/cadrumo/adapters/outbound/google/tests/` (271
passed, 2 failed — both pre-existing and unrelated: a missing modelo-303
casilla-500 Spanish locale key surfacing through `test_compute_from_pull.py`,
traceable to in-flight peer registry work visible in `git status` on
`_legal.py` / `_schema_references.py` / `iva/_classification.py` /
`place_of_supply/2025.toml`; and the new `test_package_module_allowlist.py`
entry this row itself adds, which is why it is fixed in this same change
rather than left red). `ruff check` / `ruff format --check` / `ty check`
green on every touched file. `basedpyright` was NOT run against these paths —
`[tool.basedpyright]` scopes only `src/cadrumo/domain` and
`src/cadrumo/application`, so `adapters.outbound.google` and
`entrypoints.cli` are outside that gate by project configuration, not by
omission here.

The Sheets "writes nothing" half of `P02.S06`'s binding proof rides these same
tests (`TestPreviewNeverWrites`,
`TestPreviewComputationReusesTheRealAdaptersOwnDiffPrimitives`); see that
row's record for why the filed-sweep half needed a separate real-store test
rather than a structural one.
