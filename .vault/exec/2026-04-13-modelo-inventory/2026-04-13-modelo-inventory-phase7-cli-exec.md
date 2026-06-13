---
name: 2026-04-13-modelo-inventory-phase7-cli
description: Phase 7 execution record — Typer subcommands list/show/applicable-to/year-plan (#108)
type: exec
tags:
  - "#exec"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-plan]]"
---

# phase 7 — CLI subcommands

## delivered

- `src/aeat/domain/modelos/_cli.py` — Typer `app` with four commands:
  `list`, `show`, `applicable-to`, `year-plan`. Every command
  supports `--json` and routes through the real registry /
  deadline engine with no test doubles.
- `src/aeat/entrypoints/cli/modelos/__init__.py` — thin re-export of the Typer
  app from `aeat.domain.modelos._cli`, matching the pattern used by
  `aeat.entrypoints.cli.deadlines`.
- `src/aeat/entrypoints/cli/__init__.py` — adds `from aeat.entrypoints.cli import modelos
  as modelos_module` and wires the sub-app into the root Typer
  instance in alphabetical position between `manual` and
  `normatives`.
- `_profile_from_autonomo` helper narrows an `AutonomoProfile` to
  the matching `TaxpayerProfile` for `year-plan` filtering.
- `test_cli.py` — CliRunner smoke tests: list (text + JSON + category
  filter), show (JSON + unknown-code), applicable-to (JSON),
  year-plan (JSON). Every test hits the real registry and real
  deadline engine.
- `pyproject.toml` — extends the existing Typer-B008 per-file ignore
  to cover `src/aeat/domain/modelos/_cli.py`, matching the documented
  treatment of `src/aeat/entrypoints/cli/**`.

## gate outcomes

- `just lint` — initially flagged 5 B008 warnings on the Typer
  argument defaults; resolved by extending the existing per-file
  ignore list.
- `just typecheck` — passed.
- `just test` — initially 1 test failed because strict pydantic v2
  rejects `list -> frozenset/tuple` coercion in
  `ModeloMetadata.model_validate`. Switched to
  `model_validate_json` which honours the declared JSON schema.
  Final: 756 passed, 1 skipped, 23 deselected.
- `just hooks` — ruff-format collapsed long-argument lines; re-run
  passed.

## deviations

None material. The test switched from `model_validate` to
`model_validate_json` to respect the strict pydantic contract the
ADR locks.

## commit

`b334637 feat(models): CLI subcommands list/show/applicable-to/year-plan (#108)`
