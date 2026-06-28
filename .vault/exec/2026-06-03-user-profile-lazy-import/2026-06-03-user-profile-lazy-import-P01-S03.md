---
tags:
  - '#exec'
  - '#user-profile-lazy-import'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S03'
related:
  - "[[2026-06-03-user-profile-lazy-import-plan]]"
---

# Author a producer-side regression probe

## Scope

- `src/aeat/application/user_profile/test_lazy_boundary.py` (new)

## Description

- Add subprocess probe asserting `import aeat.application.user_profile`
  in a fresh interpreter places zero
  `aeat.domain.calculations.registry*` modules into `sys.modules`.
- Mirror the consumer-side gate at
  `src/aeat/entrypoints/cli/test_lazy_command_tree.py` at the producer
  boundary so a future eager-import regression on the application
  package reds here before it reds the CLI-level surface.
- Probe is exercised against the unfixed boundary by design (it reds
  against the 69-submodule registry pull until P02 lands).

## Outcome

- File landed as commit `a0ca66a47`.
- Against unfixed boundary: probe reds with the expected 69-module
  leak signature.
- Against post-P02 boundary: probe greens (registry pull at 0).

## Notes

- Subprocess-based to avoid pytest's module-cache pollution; uses the
  same `subprocess.run([sys.executable, "-c", textwrap.dedent(code)])`
  shape as the CLI-side gate for consistency.
- Marked `pytest.mark.unit, pytest.mark.domain_application` to match
  the package's existing test surface.
