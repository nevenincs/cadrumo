---
tags:
  - '#exec'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:58efe9c3529b47be85b09c3c1bf4fdcafd2a0dfdede95b4f3335b2dbf9f6f1ca'
step_id: 'S20'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-08-09-m303-carry-reconciliation-payment-election-s20-audit]]"
---
# S20 payment-election implementation

## Scope

- `src/cadrumo/core/`
- `src/cadrumo/application/modelo/`
- `src/cadrumo/application/filing/`
- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/locales/`

## Description

- Retain the canonical `PaymentElection` type and route I, U, and G through the shared fail-closed result-disposition resolver.
- Keep `RefundElection` limited to C and D semantics; reject non-default election axes that the computed result cannot consume.
- Thread semantic elections through export, quickfile, filing, CLI, review-package, and work-file boundaries.
- Replace the ambiguous CLI option with `--refund-election` and `--payment-election` without a compatibility alias.
- Persist only the resolved result disposition and applicable semantic election in the export receipt and `MODELO_EXPORTED` event.
- Prove public U export reaches the persisted charge-account projection and charge-only DID composer; prove missing charge and G refuse.

## Outcome

S20 is complete. Positive M303 results resolve to I or U through one authority, while G is typed and capability-refused. C/D carry behavior remains separate from U/G. Receipt and event provenance contain semantic election data without account material. The formal review found and the implementation remediated a zero-result `DEVOLVER` silent-ignore path; no open S20 finding remains.

## Verification

`uv run --no-sync pytest -q src/cadrumo/application/modelo/tests/test_export_output_paths.py src/cadrumo/application/modelo/tests/test_export_result_disposition.py src/cadrumo/application/modelo/tests/test_domiciliacion_export_refused.py`

`29 passed in 41.09s`

`uv run --no-sync pytest -m integration -q src/cadrumo/entrypoints/cli/tests/test_modelo_export_verb.py::test_export_help_advertises_local_only src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py::test_quickfile_m303_fully_taxable_ledger_reaches_granted_boe_without_prorrata_input src/cadrumo/entrypoints/cli/tests/test_app_quickfile.py::test_quickfile_help_exposes_explicit_result_elections src/cadrumo/entrypoints/cli/tests/test_modelo_work_ux.py::test_work_file_help_exposes_explicit_result_elections src/cadrumo/entrypoints/cli/tests/test_modelo_review_package_verb.py::test_review_package_help_advertises_local_only`

`5 passed in 17.85s`

`uv run --no-sync ruff check` on the S20 production and test scope

`All checks passed!`

`uv run --no-sync basedpyright` on the S20 core and application production scope

`0 errors, 0 warnings, 0 notes`

`uv run --no-sync python -m dev.locales scaffold --check`

`ca.yml: ok; en.yml: ok; es.yml: ok; hu.yml: ok`

`uv run --no-sync vaultspec-core vault check all`

`ok structure: clean; ok frontmatter: clean; ok markdown: clean; ok links: clean; ok adr-status: clean`

## Notes

The shared index already carried a staged deletion for `src/cadrumo/core/_payment_election.py`, while the byte-identical canonical file existed in HEAD and is restored in the working tree. This execution did not alter the shared index; final payload assembly must retain the working-tree canonical file deliberately. The broad Vault check returned pre-existing corpus warnings outside S20 and did not block its structural checks.
