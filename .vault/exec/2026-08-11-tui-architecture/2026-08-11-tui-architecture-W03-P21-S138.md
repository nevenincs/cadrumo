---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:218dc2199e984b233c82988f1fcefaebac0c057cf30de20d61d1fb5464b345f2'
step_id: 'S138'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Implement the sole ModeloEditContractC3DependencyReceiptV1 validator with exact C2 predecessor, contract schema, baseline, guarded persistence, result-receipt, conformance, financial-handoff, production-definition, no-legacy, and redeclaration checks while leaving receipt minting to the C3 custody phase

## Scope

- `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`

## Changes

- `A` `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py -q -n 0 -m "integration or unit"` -> `pass` (52 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py` -> `pass`

## Notes

The C3 receipt's schema (`ModeloEditContractC3DependencyReceiptV1`) and its
validator (`validate_modelo_edit_contract_c3_dependency_receipt`) are both
defined in this test module rather than under `src/`, matching the sibling
C1 shape (`test_financial_operand_dependency_receipt.py`): the live tree is
the evidence, not a recorded claim, and this Step's own text defers minting
the durable `.vault/reference/2026-08-24-modelo-edit-contract-c3-dependency-receipt.md`
artifact to the C3 custody phase.

`c2_predecessor_proof` resolves to a real, discriminated `NOT_APPLICABLE`
today: `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`
does not exist yet in this tree. ADR D8 explicitly permits this ADR's own
acceptance ahead of that receipt, but a fabricated `PASSED` would misstate an
unmeasured required dependency; a dedicated test
(`test_c3_receipt_reports_the_c2_predecessor_honestly`) proves the honest
`NOT_APPLICABLE` shape and will need re-deriving once the C2 receipt lands.
This is not a blocker for this Step -- it is the Step's own predecessor
condition, faithfully reported rather than assumed.
