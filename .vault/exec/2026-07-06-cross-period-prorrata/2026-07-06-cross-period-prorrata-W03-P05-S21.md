---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:ef04f6e03ff4ae29ac97dadbb9af8e368832c562503213a74a88fd655df8eb1f'
step_id: 'S21'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add a byte-identical regression proving a non-prorrata (fully-taxable) taxpayer's deducible aggregation is unchanged from today

## Scope

- `src/aeat/application/aggregation/tests/test_iva_ledger_prorrata_apportionment.py`

## Description

- Add the dedicated prorrata apportionment regression file under the aggregation test package.
- Seed a real encrypted transaction catalogue with a fully taxable domestic purchase.
- Capture canonical IVA aggregation JSON and binding-value bytes before any prorrata register exists.
- Persist a real `ninguna` prorrata register entry for the same ejercicio and assert the same aggregation and binding payloads remain byte-identical.
- Avoid hand-computed cuota expectations; the oracle is equality against the pre-prorrata shared-path output.

## Outcome

- Completed `W03.P05.S21`.
- Verification passed:
  - `uv run --no-sync ruff check src\aeat\application\aggregation\tests\test_iva_ledger_prorrata_apportionment.py`
  - `uv run --no-sync pytest -q src\aeat\application\aggregation\tests\test_iva_ledger_prorrata_apportionment.py -n 0`

## Notes

- No production code changed.
- No incidents, data loss, skipped work, or scaffolds.
- Feature index was rebuilt with `vaultspec-core vault feature index -f cross-period-prorrata --json`.
- `vaultspec-core vault check features -f cross-period-prorrata --json` and `vaultspec-core vault check frontmatter --json` are clean.
- `vaultspec-core vault check annotations -f cross-period-prorrata --json` no longer reports the S20/S21 exec records; remaining annotation warnings are inherited from older cross-period-prorrata vault documents.
