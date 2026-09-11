---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:d50c923e12c980b0eea15b264c3c5ce3dc1dbc6e239da381aae52d2ac42b1f32'
step_id: 'S03'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Separate developer readiness probes from environment mutation

## Scope

- `dev/env`

## Changes

- `A` `dev/env/doctor.py`
- `A` `dev/env/tests/test_doctor.py`
- `M` `dev/env/__init__.py`
- `M` `dev/env/__main__.py`
- `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/audit/tests/test_complexity_scan.py dev/env/tests/test_doctor.py dev/quality/tests/test_suite_gate_table.py dev/audit/tests/test_advisory_report.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.env doctor` -> `pass`
