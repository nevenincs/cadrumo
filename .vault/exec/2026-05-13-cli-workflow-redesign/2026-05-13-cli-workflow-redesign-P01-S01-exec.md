---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P01.S01'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P01.S01`

Renamed the Typer app and its callback/command identifiers from
`doctor` to `repair` inline in the existing config entrypoint module.

- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

The plan named `src/aeat/entrypoints/cli/_config/doctor.py` as the
rename source, but no such standalone module exists in this worktree.
The doctor Typer app, its callback, and its three subcommands
(`logs`, `quarantine`, `connectivity`) live inline in
`_config/__init__.py`. The rename was performed in place: the
`doctor_app` Typer instance becomes `repair_app` with `name="repair"`
and `help=tr("cli.config.repair.help")`, the callback function and
the three subcommand handlers move from `doctor*` to `repair*`, and
every `tr("cli.config.doctor.*")` key flips to
`tr("cli.config.repair.*")`. No backwards-compat alias is left
behind. The application-layer helper imports
`build_config_doctor_report` and `render_config_doctor_text` are
left untouched because their bodies live in `application/diagnostics.py`,
which P01 is explicitly forbidden from touching (P02/P04 own them).

A `git mv` was not used because no standalone source file exists to
rename; history is preserved by the in-place edit inside the
existing `__init__.py`.

## Tests

Tests under `src/aeat/entrypoints/cli/` were rewired to invoke
`config repair` in the same step where they invoked `config doctor`;
see `P01.S05` for the test rewrite record.
