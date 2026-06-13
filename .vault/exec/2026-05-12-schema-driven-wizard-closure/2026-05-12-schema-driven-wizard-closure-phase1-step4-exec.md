---
tags:
  - '#exec'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-closure-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# c4 remove top-level version command at the cli root

## scope

C4 closes the standing config-plus-app-only rule violation: the CLI
root carried a top-level ``version`` Typer command alongside the
``--version`` / ``-V`` flag. The flag and the command served the
same surface; removing the command leaves a clean two-subgroup root
(``config`` + ``app``).

## files owned

- ``src/aeat/entrypoints/cli/__init__.py`` — the
  ``@app.command("version") version_cmd`` registration (lines
  96-105) is deleted. The root callback's ``--version`` / ``-V``
  branch is unchanged; ``build_cli_version_report`` and
  ``render_cli_version_text`` remain imported because the flag
  branch still consumes them
- ``src/aeat/entrypoints/cli/test_workflow_surface.py`` —
  ``test_version_command_can_emit_typed_json_report`` is deleted
  (its ``--format json version`` invocation exercised the deleted
  command's JSON path). ``test_version_surfaces_render_backend_registry_summary``
  is renamed to ``test_version_flag_renders_backend_registry_summary``;
  the parametrized argv list drops the bare ``["version"]`` entry
  and keeps ``["--version"]`` and ``["-V"]``

## acceptance gates run

- ``aeat --help`` shows exactly two subgroups in the Commands block:
  ``config`` and ``app``. The previous third row (``version``) is
  gone
- ``aeat --version`` and ``aeat -V`` still print the version string
  and registry summary
- ``aeat version`` exits with code 2 and the ``No such command 'version'``
  message
- ``pytest src/aeat/entrypoints/cli/test_workflow_surface.py::test_version_flag_renders_backend_registry_summary``
  — passes (the renamed test pins the flag's behaviour against the
  live :func:`build_cli_version_report`)
- ``ruff check`` and ``ty check`` on the two owned files — green

## notes

The locale catalogues still carry ``cli.root.version_command_help``
under the four files because removing it lives in the locale layer
and not in C4's scope. The translation audit walks
:mod:`aeat.entrypoints.cli` for referenced keys, so the dead key
does not appear in the audit's failure set and does not surface
through any operator-facing help string.

The concurrent-agent ``test_error_boundary_integration.py`` file is
untracked and still references ``["version"]`` as a probe argv. That
file is off-limits to this closure plan; the concurrent agent will
update it when their work lands.
