---
tags:
  - '#exec'
  - '#schema-driven-wizard-revision'
date: '2026-05-12'
modified: '2026-07-17'
body_hash: 'sha256:1602f328687baf3a44a807b0a8cffb6d2450e02a340513906f2bf3c1580e4a8a'
related:
  - "[[2026-05-12-schema-driven-wizard-revision-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# r1 strip transient-process-state markers from test_config_setter

## scope

R1 removes the transient-process-state markers from the new wizard
CLI test surface. The plan calls out the `xfail` reference and the
`W12` comment in `test_config_setter.py` lines 6-7. The case-
insensitive lookup landed via the `ProfileKey.from_key` boundary, so
the test is a plain pass with no rollout-state gate.

## files owned

- `src/aeat/entrypoints/cli/test_config_setter.py` — module docstring
  rewritten to describe the executable behaviour instead of the
  rollout-stage gate

## acceptance gates run

- `pytest src/aeat/entrypoints/cli/test_config_setter.py` — passes
  (5 tests)
- `pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_cli_unit_tests_do_not_contain_process_state_or_xfail_language`
  — passes
- `grep -n 'W[0-9]\|xfail\|previously\|legacy' src/aeat/entrypoints/cli/test_config_setter.py`
  — returns nothing

## notes

The `pytest.mark.unit` and `pytest.mark.domain_application` markers
remain; they are mode metadata, not process-state language.
