---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P01.S04'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P01.S04`

Updated CLI-emitted help text and recovery copy that named
`aeat config doctor` to name `aeat config repair` instead.

- Modified: `src/aeat/entrypoints/cli/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

The repair callback docstring now reads
`Diagnose and repair local configuration, registry, profile, auth,
and log state.`, covering the diagnose-plus-act surface the ADR
mandates. The startup-import-failure stderr text in the CLI root
module flips its recovery hint from `Run: aeat config doctor` to
`Run: aeat config repair`. The translation calls in the repair
Typer app reference the `cli.config.repair.*` key family; the
locale YAML files that resolve those keys are renamed under P05.

The boundary recovery suggestions in
`src/aeat/entrypoints/cli/_errors.py` no longer carry the
hardcoded `aeat config doctor` string at all; the validation and
unexpected boundary errors now place the error type and detail in
their context rather than a recovery command. No edit was needed
in this step beyond what landed there already.

## Tests

The pair `test_config_repair_is_config_scoped_not_root` and
`test_startup_import_failure_points_to_config_repair_without_traceback`
in `test_workflow_surface.py` lock the rendered command string.
