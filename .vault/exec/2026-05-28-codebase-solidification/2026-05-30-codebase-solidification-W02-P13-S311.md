---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S311'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P13.S311`

Added `CAST-RATIONALE-WIZARD-COMMAND-INJECT` marker at the `typing.cast(typing.Any, _command)` site in the wizard command builder.

- Modified: `src/aeat/application/wizard/_commands.py`

## Description

Typer resolves CLI parameters from `__signature__` at decoration time. The `cast` to `Any` is required to allow dynamic `inspect.Signature` assignment without mypy rejecting the immutable `Callable` type. The comment is placed immediately above the `typed = typing.cast(...)` line, satisfying the inventory test's one-line lookback.

## Tests

`src/aeat/test_cast_rationale_inventory.py` confirms the site carries its marker.
