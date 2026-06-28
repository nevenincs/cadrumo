---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P01.S05'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P01.S05`

Renamed every `doctor`-flavoured CLI test name and invocation string
inside `src/aeat/entrypoints/cli/` to the redesigned `repair`
namespace. No dedicated `_config/test_doctor.py` module exists in
this worktree; the surface coverage lives in cross-cutting tests
under `entrypoints/cli/`.

- Modified: `src/aeat/entrypoints/cli/test_workflow_surface.py`
- Modified: `src/aeat/entrypoints/cli/test_root_help_shape.py`
- Modified: `src/aeat/entrypoints/cli/test_apex_workflow_verification.py`
- Modified: `src/aeat/entrypoints/cli/test_error_boundary_integration.py`

## Description

`test_config_doctor_is_config_scoped_not_root` and
`test_startup_import_failure_points_to_config_doctor_without_traceback`
in `test_workflow_surface.py` were renamed to the `repair`
counterparts; every Typer invocation string flipped to
`["config", "repair", ...]` and the import-failure stderr
assertion now expects `aeat config repair`. The negative
`test_retired_commands_are_not_registered` list keeps the
`["doctor", "--help"]` and `["config", "doctor", "--help"]`
entries because they now assert the absence of the old namespace,
which is exactly the redesign contract; a new
`["config", "repair-logs", "--help"]` row joins them.
`test_root_help_shape.py` flips its `aeat config doctor` substring
assertion. `test_apex_workflow_verification.py` flips its
`config_children` subset to include `repair` instead of `doctor`.
`test_error_boundary_integration.py` flips its two parametrised
Typer invocation lists from `"config", "doctor"` to
`"config", "repair"`.

A `git mv` was not used because no standalone `test_doctor.py`
file exists.

## Tests

The renamed tests carry the same assertions as their predecessors;
only the command string under test changes.
