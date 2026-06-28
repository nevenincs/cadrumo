---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P01.S06'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P01.S06`

Ran the repo-wide grep gate over `src/aeat/entrypoints/cli/` for the
surviving `doctor` token, the `config doctor` phrase, and any
`from .*doctor` import. Documented every survivor with the phase
that owns its rename.

## Description

After the P01 rename the surviving `doctor` references inside
`src/aeat/entrypoints/cli/` are:

- `test_workflow_surface.py` lines 206, 235, 236. The string
  `"doctor"` and the lists `["config", "doctor", "--help"]` and
  `["config", "doctor-logs", "--help"]` live inside the
  `test_root_surface_contains_config_and_app_only` removed-command
  list and the `test_retired_commands_are_not_registered`
  removed-command list. Both lists assert the absence of the old
  namespace, which is exactly the redesign contract. These are
  intentional negative-coverage rows, not survivors that need
  renaming.
- `_root_landing.py` line 42. The translation key
  `cli.root.landing.quick_start_doctor` is a locale identifier
  resolved through `tr(...)`. The key string itself is renamed
  under P05 in lockstep with the four locale YAML files; touching
  the key in isolation would break the locale lookup until P05
  lands.
- `_config/__init__.py` lines 14, 18, 67, 68. The imports
  `build_config_doctor_report` and `render_config_doctor_text`
  name application-layer symbols in
  `src/aeat/application/diagnostics.py`. P01 is explicitly
  forbidden from touching the diagnostics body; the rename of those
  helper symbols is owned by P02 / P04.

No `from .*doctor` import statements remain inside
`src/aeat/entrypoints/cli/`.

## Tests

The grep gate is the verification itself; the documented survivors
are all either negative-coverage rows or locale-key / application-
symbol references that downstream phases own.
