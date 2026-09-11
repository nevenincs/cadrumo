---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:ac68043eeef5f5309001003103ffc26b1a255182306f89b26e34fd244dc07a34'
step_id: 'S06'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Narrow the quality suite to blocking code-quality verdicts

## Scope

- `dev/quality`

## Changes

- `M` `dev/quality/suite.py`
- `M` `dev/quality/tests/test_suite_gate_table.py`
- `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/quality/tests/test_suite_gate_table.py dev/audit/tests/test_advisory_report.py dev/audit/tests/test_dead_code.py` -> `pass`
