---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W47.P231'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-app-modelo-bindings-shape-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W47.P231`

Locked the binding-shape grammar at the CLI boundary by replacing
the legacy single-command `aeat app modelo bindings ...` with a
sub-Typer group that exposes `list` and `preview` subcommands.

- Modified: `src/aeat/entrypoints/cli/_modelo.py`

## Description

Grammar locked:

- `aeat app modelo bindings list --modelo M --year YYYY --period P
  [--missing]` — lists required and available binding keys with a
  readiness column derived from the binding source kind. The
  closed readiness vocabulary is `ledger source`, `profile fact`,
  `prior filed revision`, `live observation`, `bucket`, `waiver`,
  `blocking finding`, and `casilla`. `--missing` filters to
  bindings that require runtime resolution (every non-
  `constant_value` source).

- `aeat app modelo bindings preview --modelo M --year YYYY
  --period P [--binding KEY=VALUE]` — resolves temporary
  `--binding KEY=VALUE` overrides without mutating state. The
  override map is parsed at the CLI boundary; raw values flow
  through unchanged so the downstream bindings-resolution layer
  can coerce per source type.

The wave landed:

- `_BINDING_SOURCE_TO_READINESS` mapping from registry source
  kinds to the closed readiness vocabulary.
- `_readiness_for_source(source)` helper with a documented
  fallback to `ledger source` for unknown sources.
- `_parse_binding_override(spec)` helper that rejects malformed
  KEY=VALUE syntax with `typer.BadParameter`.
- `bindings_app` Typer registered under the parent `aeat app
  modelo` Typer via `app.add_typer(bindings_app, name="bindings")`.

Unknown override keys fail with a suggestion list sourced from
the registry's binding catalogue for the active modelo / year /
period.

The existing `test_modelo.py::test_malformed_period_surfaces_as_bad_parameter`
parametrisation is updated to drive the new flag grammar.

Closed plan rows: `W47.P231.S1381`, `W47.P231.S1382`,
`W47.P231.S1383`, `W47.P231.S1384`, `W47.P231.S1385`,
`W47.P231.S1386`.

## Tests

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_modelo.py
-q` — 11 / 11 pass (4 pre-existing + 7 W47 additions).
