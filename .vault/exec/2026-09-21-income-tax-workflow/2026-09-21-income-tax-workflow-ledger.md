---
tags:
  - '#exec'
  - '#income-tax-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:44cd054d53016d7fe6fac9cd3eabb9b62a3293df1a00fdd8c2dabed5456527a4'
related:
  - "[[2026-09-21-income-tax-workflow-plan]]"
---

# `income-tax-workflow` ledger

## Changes

- `S01` `A` `dev/acceptance/__init__.py`
- `S01` `A` `dev/acceptance/income_tax/__init__.py`
- `S01` `A` `dev/acceptance/income_tax/authority.py`
- `S01` `A` `dev/acceptance/income_tax/tests/__init__.py`
- `S01` `A` `dev/acceptance/income_tax/tests/test_authority.py`
- `S01` `verify:` `python -m dev.acceptance.income_tax.authority --latest-supported --as-of 2026-09-21` -> `pass`
- `S01` `verify:` `python -m pytest -q dev/acceptance/income_tax/tests/test_authority.py` -> `pass`
- `S01` `verify:` `ruff check dev/acceptance/income_tax` -> `pass`
- `S02` `A` `dev/acceptance/income_tax/scenario.py`
- `S02` `A` `dev/acceptance/income_tax/tests/test_scenario.py`
- `S02` `verify:` `uv run --no-sync ruff check dev/acceptance/income_tax/scenario.py dev/acceptance/income_tax/tests/test_scenario.py` -> `pass`
- `S02` `by:` `root`
- `S03` `M` `dev/acceptance/income_tax/scenario.py`
- `S03` `M` `dev/acceptance/income_tax/tests/test_scenario.py`
- `S03` `A` `dev/acceptance/income_tax/cli_journey.py`
- `S03` `A` `dev/acceptance/income_tax/tests/test_cli_journey.py`
- `S03` `verify:` `python -m dev.acceptance.income_tax.cli_journey --year 2025 [isolated installed CLI]` -> `pass`
- `S03` `by:` `coordinator`
- `S04` `verify:` `vaultspec-core status tuimodelo` -> `fail`
- `S04` `by:` `coordinator`

## Notes

- `S01` M100/2025 XML export is deliberately blocked: application.filing.export_parity.errors.aux_block_undeclared (aux_version); no value was invented.
- `S03` Partial evidence: installed CLI proves A1, quarterly A3/A4, annual A6 calculation/verification, and four M130 exports; M100 export is blocked by undeclared aux_version. Controlled mutation and isolated missing-history variant remain unexercised, so P02.S03 stays open.
- `S04` Blocked prerequisite: canonical tuimodelo plan is 24/173 steps complete with next W02.P05.S18. Installed Modelo workspace is read-only and lacks calculation, verification, filing, and export actions; required accepted-plan dependencies begin at W02.P07.S30/S31 and W04.P14 onward. No second rollout or out-of-order closure was created.
