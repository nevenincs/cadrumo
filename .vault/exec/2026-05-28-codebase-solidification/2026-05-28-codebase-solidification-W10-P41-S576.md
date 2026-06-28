---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S576
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W10.P41.S576`

Added `ANY-RETURN-RATIONALE-CATALOGUE-SLOT` markers on `get_setup_flow` and `get_wizard_flows` in `core/profile_catalogue.py`.

- Modified: `src/aeat/core/profile_catalogue.py`

## Description

Both functions return `Any` because the concrete wizard-flow type is registered at runtime via `register_wizard_catalogue` and is not importable from `aeat.core` without introducing a circular import. The inline rationale markers on the def lines document this boundary constraint.

## Tests

W10 inventory test parametrizes both function names and asserts marker presence. 27/27 passed.
