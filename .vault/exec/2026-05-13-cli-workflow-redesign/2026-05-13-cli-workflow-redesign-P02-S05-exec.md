---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P02.S05'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P02.S05`

Verified the JSON `--format json` path surfaces both `next_action`
and `dead_end` on every `DiagnosticCheck` through Pydantic's
`model_dump`.

- Verified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Verified: `src/aeat/application/diagnostics.py`

## Description

The redesigned `aeat config repair` root callback emits the report
via:

```python
_emit(ctx, report.model_dump(mode="json"), render_config_doctor_text(report).splitlines())
```

`ConfigDoctorReport.checks` is `tuple[DiagnosticCheck, ...]`. With
`dead_end` declared as a model field on `DiagnosticCheck`, the
default `model_dump(mode="json")` serialises both `next_action` and
`dead_end` as explicit JSON keys (value `null` when unset).

A dedicated test asserts the contract:
`test_diagnostic_check_model_dump_surfaces_both_recovery_fields`.

P03 owns the new `reset-state` Typer command; the JSON-emit
contract is unchanged for that subcommand and does not need a
parallel touch here. The legacy plan reference to
`src/aeat/entrypoints/cli/_config/repair.py` is obsolete — P01
collapsed `repair` back inline into `_config/__init__.py`, and the
JSON serialisation already routes through that module.

## Confirmation

- `pytest src/aeat/application/test_diagnostics.py::test_diagnostic_check_model_dump_surfaces_both_recovery_fields`
  passes.
- No further `_emit` wiring required; the explicit-field serialisation
  is provided automatically by Pydantic.
