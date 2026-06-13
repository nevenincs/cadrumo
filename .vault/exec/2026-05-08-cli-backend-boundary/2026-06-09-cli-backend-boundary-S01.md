---
step_id: S01
tags:
  - '#exec'
  - '#cli-backend-boundary'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-05-08-cli-backend-boundary-plan]]'
  - '[[2026-05-08-cli-backend-boundary-reference]]'
---

# `cli-backend-boundary` S01: purge process-state/skip language from CLI tests

## Summary

Resolved 6 hygiene-gate offences flagged by
`test_backend_boundary.py::test_cli_unit_tests_do_not_contain_process_state_or_xfail_language`.
The gate scans every `test_*.py` under the CLI test tree for forbidden phrases
(`stub`, `xfail`, `deferred`, `pytest.skip`, etc.) that indicate process-state
or skip-oriented language rather than executable-behaviour description.

## Offences and fixes

| File | Offending term | Why it was there | Fix chosen |
|------|---------------|-----------------|------------|
| `test_documented_command_conformance.py` | `xfail` | Module docstring listed forbidden test-double vocabulary as a "we don't do this" disclaimer | Reworded to "No test doubles" |
| `test_documented_command_conformance.py` | `stub` (×2) | Inline docstring/comment called a narrative reference an "ellipsis stub" | Renamed to "ellipsis reference" / "ellipsis placeholder" |
| `test_ledger_llm_classify.py` | `xfail` | Module docstring boilerplate "No mocks, stubs, skips, xfail, or monkeypatch" | Reworded to "No test doubles or monkeypatch" |
| `test_live_read_subgroups.py` | `pytest.skip` (×2) | Helper `_live_process_command_lines()` skipped if PowerShell or `ps` was not on PATH | Replaced with `RuntimeError` — a missing system tool is a broken environment, not a skip condition |
| `test_modelo_210_stub_refusal.py` | `deferred` | Inline comment "context for deferred rendering by the CLI layer" | Replaced with "lazy rendering" — technically equivalent, avoids the banned term |
| `test_modelo_work_ux.py` | `xfail` | Docstring note "Left failing loudly (no skip/xfail)" — the parenthetical itself contained the banned word | Removed parenthetical, kept intent sentence |

## Verification

- Pattern check via Python script replicating gate logic: all five files CLEAN.
- Gate: `test_cli_unit_tests_do_not_contain_process_state_or_xfail_language` — **1 passed in 1.98s**.
- All 87 tests across the five affected files — **87 passed in 79.93s**.

## Commit

`f0aaf8654` — `test(cli): purge process-state/skip language from CLI tests (backend-boundary hygiene gate)`
