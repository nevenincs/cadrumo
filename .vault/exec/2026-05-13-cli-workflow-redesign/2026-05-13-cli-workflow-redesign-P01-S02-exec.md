---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P01.S02'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P01.S02`

Rewired the `aeat config` Typer root to mount the repair Typer app
under the name `repair` in place of the old `doctor` mount.

- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

The single `app.add_typer(doctor_app, name="doctor")` call at the
bottom of the config entrypoint module is replaced by
`app.add_typer(repair_app, name="repair")`. There is no alias
mount, no second `add_typer` line keyed on `name="doctor"`, and no
deprecation shim. After this step, invoking `aeat config doctor`
returns the Typer unknown-command exit code path; invoking
`aeat config repair` resolves to the renamed app.

## Tests

`test_config_repair_is_config_scoped_not_root` in
`src/aeat/entrypoints/cli/test_workflow_surface.py` asserts that
`config repair --help` succeeds and `config doctor` is rejected.
