---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:7f0d26d9715994894371e5f3c94876b371e04ee75977c7070e00b51010c284d9'
step_id: 'S06'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

# add a real-CLI end-to-end test that a fully-taxable M303 trader reaches a granted `.boe` with no prorrata-divergence error and no manual prorrata input

## Scope

- `src/aeat/application/modelo/tests/`

## Description

- Add real CLI `app quickfile` coverage for Modelo 303 2026 1T.
- Seed a real active profile, real encrypted-SQLite ledger transactions, linked purchase-invoice evidence, and a neutral IVA wallet decision.
- Invoke the public quickfile chain without `--casilla`, without any `iva.prorrata*` input, and without manual prorrata bindings.
- Assert calculate, verify, and export stages succeed, `granted_verificado_completo` is true, the `.boe` file is written, the taxpayer NIF is present in the exported bytes, and no notice contains `prorrata`.

## Outcome

Completed the executable S06 proof in `src/aeat/entrypoints/cli/tests/test_app_quickfile.py`.

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_app_quickfile.py` -> passed.
- `python -m py_compile src/aeat/entrypoints/cli/tests/test_app_quickfile.py` -> passed.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_app_quickfile.py::test_quickfile_m303_fully_taxable_ledger_reaches_granted_boe_without_prorrata_input` -> `1 passed in 27.07s`.
- `uv run --no-sync pytest -q -m integration src/aeat/entrypoints/cli/tests/test_app_quickfile.py` -> `4 passed in 32.58s`.

## Notes

The originating plan row names `src/aeat/application/modelo/tests/`, but the load-bearing S06 requirement is explicitly real CLI end-to-end behaviour. The existing quickfile integration harness is the executable public surface for create -> calculate -> verify -> export, so the proof lives with the CLI quickfile tests rather than duplicating a service-level path.

The first M303 quickfile attempt reached `granted_verificado_completo=true` but export refused because the deductible ledger purchase row intentionally requires linked purchase invoice evidence before `.boe` export. The final fixture adds that real invoice evidence, preserving the filing-grade gate while allowing export.

Do not infer a plan checkbox from this file alone: `vaultspec-core vault plan step check 2026-06-19-silent-zero-base-aggregation-plan S06` was not run because `.vault/plan/2026-06-19-silent-zero-base-aggregation-plan.md` already had non-authored WIP before the step-check edit window.
