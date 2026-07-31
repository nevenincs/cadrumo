---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:03ab3f7c2ad72c5d66916b3c21b5d2feb5943b62d63afed953bec7d6b8c718c0'
step_id: 'S20'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# carry the applied percentage and its provenance on the binding value provenance and the casilla observation trail (binding-values-carry-provenance)

## Scope

- `src/aeat/application/aggregation/_modelo_bindings.py`

## Description

- Preserve the prorrata register's applied percentage provenance, source-observation identity, and reference metadata on the IVA apportionment DTO.
- Emit an existing `CalculationSourceProvenance` row from the IVA source-mesh resolver for the applied general-prorrata percentage, using the existing `ledger_iva_aggregation` source kind.
- Carry the registry legal/source grounding for the deducible cuota casillas qualified by the apportionment row, without overloading cross-period `source_casilla_ids`.
- Add a real secure-repository resolver regression proving a persisted prorrata register entry produces the percentage/provenance source trace.
- Append the S20 implementation review to the campaign audit.

## Outcome

- Completed `W03.P05.S20`.
- No new binding source kind, resolver convention, validator convention, or registry selector shape was introduced.
- Verification passed:
  - `uv run --no-sync ruff check src\aeat\application\aggregation\_iva_ledger.py src\aeat\application\aggregation\_modelo_bindings.py src\aeat\application\aggregation\tests\test_modelo_source_mesh_ledger.py`
  - `uv run --no-sync pytest -q src\aeat\application\aggregation\tests\test_modelo_source_mesh_ledger.py -k prorrata_apportionment -n 0`
  - `uv run --no-sync pytest -q src\aeat\application\aggregation\tests\test_modelo_source_mesh_ledger.py -n 0`
  - `uv run --no-sync pytest -q src\aeat\application\aggregation\tests\test_iva_ledger.py -n 0`

## Notes

- No incidents, data loss, skipped work, or scaffolds.
- The regression avoids a hand-computed cuota expected value; it asserts the source provenance contract and relies on later field-flow/oracle steps for calculation-value assertions.
- Feature index was rebuilt with `vaultspec-core vault feature index -f cross-period-prorrata --json`.
- `vaultspec-core vault check features -f cross-period-prorrata --json` and `vaultspec-core vault check frontmatter --json` are clean.
- `vaultspec-core vault check all --feature cross-period-prorrata --json` still reports inherited/out-of-scope vault hygiene: fresh-clone modified-stamp info, pre-existing template annotations in older cross-period-prorrata documents, global feature-rename-integrity errors in unrelated exec folders, and the existing unreferenced research / plan-no-research warnings for this feature.
