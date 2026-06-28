---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W47.P234'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W47.P234`

Real-behaviour verification. Five new tests drive the `list` and
`preview` surfaces through Typer's `CliRunner` against the
committed registry on disk.

## Description

Suite breakdown (additions to
`src/aeat/entrypoints/cli/test_modelo.py`):

- `test_bindings_list_emits_readiness_category_for_every_row`
  asserts every binding row carries a readiness column from the
  closed vocabulary. Verified against Modelo 303 where every
  binding sources from `ledger_iva_aggregation` and so resolves
  to `ledger source`.
- `test_bindings_list_missing_filter_excludes_constant_value_bindings`
  exercises the `--missing` filter and pins the JSON-payload
  contract `missing_filter\tTrue`.
- `test_bindings_preview_echoes_override_for_known_key` passes a
  real binding id with a Decimal override and asserts the value
  surfaces in the `override` column.
- `test_bindings_preview_rejects_unknown_binding_with_suggestion_list`
  pins the suggestion-list contract: an unknown override key
  must produce a CLI error containing the unknown key and at
  least one known binding id from the active modelo / year /
  period.
- `test_bindings_preview_rejects_malformed_override_syntax`
  pins the boundary-error contract: a `--binding` without `=`
  fails with `KEY=VALUE` in the error text.

The existing `test_malformed_period_surfaces_as_bad_parameter`
parametrisation is updated to drive the new `list --modelo M
--year YYYY --period P` flag grammar; the malformed-period
contract is preserved.

Closed plan rows: `W47.P234.S1399`, `W47.P234.S1400`,
`W47.P234.S1401`, `W47.P234.S1402`, `W47.P234.S1403`,
`W47.P234.S1404`.

## Tests

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py
-q` — 11 / 11 pass.
