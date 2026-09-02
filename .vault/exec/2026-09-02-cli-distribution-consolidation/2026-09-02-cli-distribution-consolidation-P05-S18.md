---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:50b3088cea1f2807d6a8a0b71d17b8b4dc22adb1282dced6d39f25fddc48dfed'
step_id: 'S18'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Add the headless self-test option and its console-capability bypass

## Scope

- `src/cadrumo/entrypoints/cli/_tui_policy.py`

## Changes

M src/cadrumo/entrypoints/cli/_tui_policy.py
M src/cadrumo/entrypoints/cli/_tui_session.py
M src/cadrumo/entrypoints/cli/_root_command_specs.py
M src/cadrumo/entrypoints/cli/_root_cli.py
M src/cadrumo/entrypoints/tui/__main__.py

## Notes

The console-capability refusal protects an interactive operator from a terminal that
cannot render. A runner proving an installed artifact starts has no terminal at all, so
the check is lowered for the self-test alone and its default leaves every existing
caller unchanged.

The session runs out of process, so the flag is carried to the child rather than acted
on in the command layer; the module-execution surface reads it and runs the session
headless.

The wiring is verified end to end: the flag is accepted, the console refusal is
bypassed, and the child session starts. It then fails inside the operation registry's
own composition, identically when the module is executed directly, so that defect is
not in this path.
