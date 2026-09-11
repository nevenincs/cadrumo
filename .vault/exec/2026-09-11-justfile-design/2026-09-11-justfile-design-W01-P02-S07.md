---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:3c227586333233c041eb0d0be52f565e3f33a1af33879de00d04bcda8b5aa445'
step_id: 'S07'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Narrow advisory composition to normalized non-blocking scanners

## Scope

- `dev/audit`

## Changes

- `M` `dev/audit/advisory.py`
- `M` `dev/audit/complexity.py`
- `M` `dev/audit/dead_code.py`
- `M` `dev/audit/duplication.py`
- `M` `dev/audit/report.py`
- `M` `dev/audit/tests/test_complexity_scan.py`
- `M` `dev/audit/security.py`
- `M` `dev/audit/tests/test_security.py`
- `M` `dev/audit/write_path_coverage.py`
- `verify:` `uv run --no-sync pytest --confcutdir=dev -q dev/audit/tests/test_complexity_scan.py dev/audit/tests/test_advisory_report.py dev/audit/tests/test_dead_code.py` -> `pass`
- `verify:` `uv run --no-sync pytest --confcutdir=dev -n0 -q dev/audit/tests/test_security.py dev/audit/tests/test_advisory_dimensions_scan.py` -> `pass`
