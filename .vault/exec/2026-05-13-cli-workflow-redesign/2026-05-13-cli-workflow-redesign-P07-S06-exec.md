---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P07.S06'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` P07.S06 — application diagnostics symbols renamed Doctor → Repair

## Finding

M-2 (MEDIUM, with L-1 fixture-name fold-in). The Pydantic model
`ConfigDoctorReport`, its builder `build_config_doctor_report`, and its
renderer `render_config_doctor_text` retained the retired `doctor`
label in their identifiers and docstrings. Test-only fixture
identifiers (`aeat.test.doctor.rotation`, `doctor-row-N`) mirrored the
same retired label.

## Resolution

Renamed every symbol consistently:

- `ConfigDoctorReport` → `ConfigRepairReport`
- `build_config_doctor_report` → `build_config_repair_report`
- `render_config_doctor_text` → `render_config_repair_text`

Updated every caller: `src/aeat/entrypoints/cli/_config/__init__.py`
(the `repair` callback's bare-invocation path now imports and calls the
renamed symbols), `src/aeat/application/test_diagnostics.py` (every
import, function name, and docstring referencing `config doctor`).

Updated docstrings in `src/aeat/application/wizard/_status.py` and
`src/aeat/core/access_gate/__init__.py` to describe `config repair`
rather than `config doctor` / `doctor surface` / `doctor renderer`.

Renamed test-only fixture identifiers in
`src/aeat/application/test_diagnostics.py`:
`aeat.test.doctor.rotation` → `aeat.test.repair.rotation`,
`doctor-row-1..4` → `repair-row-1..4`.

No backwards-compat aliases were retained; no `# noqa` or
`# type: ignore` was introduced.

## Verification

`pytest src/aeat/application/` runs green after the rename; the public
`__all__` exports list of `diagnostics.py` lists the renamed symbols
only.
