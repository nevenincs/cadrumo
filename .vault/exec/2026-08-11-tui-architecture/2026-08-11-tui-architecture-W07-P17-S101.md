---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:6ee8ec98e93ec53631df5f389b7665fac3c6b3d17556cc63b24b4b39755d405e'
step_id: 'S101'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Run the packaged TUI through its installed console and module entrypoints without importing CLI internals

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py`

## Changes

- `verify:` `pytest tui/tests/test_installed_entrypoint.py test_module_execution.py test_launcher_entry_point.py` -> `9 passed`

## Notes

No file changed. The gate this row names already exists and covers all three
clauses: `test_the_packaging_declares_the_dedicated_console_entry_point`,
`test_the_installed_console_script_starts_a_session` (a real full-screen
session through the console wrapper, not an in-process call), and
`test_starting_through_the_entry_point_imports_no_cli_internals`, which
resolves the entry point the way the wrapper does and asserts no
`cadrumo.entrypoints.cli` module is imported. The module form is covered by
`test_module_execution.py`.

Closed on verification. Independently reproduced the central property before
reading the gate: importing `entrypoints.tui.launcher` in a clean interpreter
leaves zero `cadrumo.entrypoints.cli` modules in `sys.modules`.
