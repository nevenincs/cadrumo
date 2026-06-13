---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S53'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
---

# `cross-period-filing-clean-state` `W07.P16.S53` exec - CLI dependency inventory

## Description

Expose the cross-period dependency inventory through `aeat app modelo work dependencies`.
The command lists registry-derived target filings for a filing year, supports modelo filtering, and evaluates active-bucket clean-state blockers when both `--modelo` and `--period` are supplied.

## Outcome

Operators can now inspect which Modelo filings require upstream filing-history evidence before verification or filing. The target read also surfaces concrete blocker codes such as `missing_current_filing_record` and `missing_observation`, using the same `evaluate_cross_period_clean_state` service and profile taxpayer id as the verification/export/file gates.

## Verification

Command passed: `uv run pytest src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py -m integration -q` with 20 tests passing.

Command passed: `uv run ruff check` on the touched CLI, payload, application, deadline, and registry surfaces.

Command passed: YAML parse check for `src/aeat/locales/en.yml` and `src/aeat/locales/es.yml`.
