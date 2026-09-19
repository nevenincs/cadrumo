---
tags:
  - '#reference'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:c022137932727424f1a053b6f6fa00ba2a84505b5a814873bdc2839670b696ec'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `tui-architecture` reference: `modelo edit contract c3 dependency receipt`

The `ModeloEditContractC3DependencyReceiptV1` for the Modelo Edit Contract V1, produced
and validated at the head recorded below. Every one of its twelve proofs derives as
`PASSED`; no field is `NOT_APPLICABLE`.

## Ancestry and what this receipt attests to

Path-scoped, not whole-tree, for the same reason its financial-operand sibling is. The
ten paths under Source ancestry were verified clean at the recorded head immediately
before stamping, and the validator ran green against exactly those contents. No claim is
made about the repository as a whole.

An unscoped whole-tree claim decays the moment anyone commits, which is how two divergent
receipts for one predecessor came to exist in this feature. A path-scoped claim stays
true while those paths are unchanged, and a reader can check it in one command.

## Reproduction

```
git status --porcelain -- <the ten paths under Source ancestry>
uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py -m unit -n0 -q
```

The first returned empty. The second returned `12 passed`.

## Predecessors

Both predecessors are bound by their own recorded verdicts rather than by filename. The
derivation parses each and refuses a document that is not green for the expected receipt
schema, so a red or reshaped predecessor breaks this receipt instead of passing as a
path that happens to exist.

The Workspace C2 predecessor was re-minted immediately before this receipt, over a
clean-commit scope derived from its fingerprinted model graph rather than hand-listed.
Its previously recorded fingerprint had drifted; this receipt binds the corrected one.

| predecessor | verdict | bound at |
| --- | --- | --- |
| `ModeloWorkspaceC2DependencyReceiptV1` | `PASSED` | `b5ba5a54d25bc48994901d4473394de9cdc83c0b` |
| `TuiOperationFinancialOperandDependencyReceiptV1` | `PASSED` | `ff03ead7cd30df1d2bd2b48386e7ab39123b425c` |

## Receipt

```json
{
  "receipt_schema": "ModeloEditContractC3DependencyReceiptV1",
  "validator": "validate_modelo_edit_contract_c3_dependency_receipt",
  "validator_module": "src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py",
  "validation_result": "PASSED",
  "receipt": {
    "schema_version": 1,
    "current_head_commit": "ea4b82a5a9f4818605508cc031a8552f7ba589c9",
    "ancestry_scope": "path_scoped",
    "governing_adr": {
      "stem": "2026-08-24-modelo-edit-contract-adr",
      "status": "accepted",
      "body_hash": "sha256:5c774af69f765a94df5b743e7cc8148dac8a38d482c69538fea7f707aeacd4fe"
    },
    "proofs": {
      "adr_status_proof": "passed",
      "adr_body_hash_proof": "passed",
      "c2_predecessor_proof": "passed",
      "contract_schema_proof": "passed",
      "baseline_proof": "passed",
      "guarded_persistence_proof": "passed",
      "result_receipt_proof": "passed",
      "conformance_proof": "passed",
      "financial_handoff_proof": "passed",
      "production_definition_proof": "passed",
      "no_legacy_proof": "passed",
      "redeclaration_proof": "passed"
    },
    "edit_compatibility_tuple": {
      "request_schema": {
        "schema_id": "modelo.edit.submission",
        "schema_version": 1,
        "schema_fingerprint": "f3e840b4cdb61a2c34c26623f69105590f1cb4fbea66a626b356615a01aba687"
      },
      "result_schema": {
        "schema_id": "modelo.edit.receipt",
        "schema_version": 1,
        "schema_fingerprint": "b1498c2f3110788bb8ebabff56a67f639887be1cf31fc3cbb0a258cdc987f089"
      }
    },
    "surface_fingerprints": {
      "ModeloEditBaselineV1": "sha256:dd07407652d676ba79c3f17426b5dd7bf58e979f939c455cf9f486ad089cce5c",
      "ModeloEditCompatibilityTupleV1": "sha256:5dd70cf41aa2b350eda1ee597bb9afd4230e71562e05ac426b4995ed2fe289ce",
      "ModeloEditMutationResultReceiptV1": "sha256:b1498c2f3110788bb8ebabff56a67f639887be1cf31fc3cbb0a258cdc987f089"
    },
    "baseline_evidence": "baseline 650c5411 carries 20 writable scalars and 0 writable row groups",
    "guarded_persistence_evidence": "a real conflicting-pointer refusal, not a simulated one",
    "result_receipt_evidence": "encrypted roundtrip plus an anti-tautology corruption refusal",
    "conformance_evidence": "modelo 131 revision 2025 carries 20 MANUAL scalars and 97 MANUAL_INPUT bindings",
    "financial_handoff_evidence": "the mutation result receipt carries no financial value, raw input, or row content field",
    "production_definition_inventory": {
      "declaring_authorities": 1,
      "operation_definition_id": "modelo.edit.apply"
    },
    "opens_c3_edit_destinations": [
      "modelo.edit.apply scalar casilla intents",
      "modelo.edit.apply binding intents",
      "modelo.edit.apply detail-row intents"
    ]
  }
}
```

## Source ancestry

Ten paths, each verified clean at the recorded head immediately before stamping.

| path | blob |
| --- | --- |
| `src/cadrumo/application/modelo/_edit_models.py` | `b1a27e1b10b1d4b044d8c5fc4a1009957d004ca3` |
| `src/cadrumo/application/modelo/_edit_services.py` | `32e55a36bc44147a83c0aefdc99d8d1d655412e7` |
| `src/cadrumo/application/modelo/_edit_execution.py` | `8a59cf2dabc4b47427895428bd0de19f3b1dcc12` |
| `src/cadrumo/application/modelo/_edit_facade.py` | `7707fa750bd06c599a2617aa16a256987c93bf36` |
| `src/cadrumo/application/modelo/_revision_persistence.py` | `e6d732a2ee443b165ff11006731f4dacc7c61784` |
| `src/cadrumo/application/modelo/operation_definitions.py` | `ea62f6c9dec60c3b1c9e4883ecae28b944154461` |
| `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py` | `6f4ed1192ea0201412a451636f211c12cf7ed9ba` |
| `.vault/adr/2026-08-24-modelo-edit-contract-adr.md` | `f8d4022f6ac9d927ee493dfc269e4694dc02f2c2` |
| `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt-reference.md` | `dd02925ed34f86ca80be9fea4e0848ab05f6ec21` |
| `.vault/reference/2026-08-28-tui-architecture-operation-financial-operand-dependency-receipt-reference.md` | `99e6260a497782e19ccc5ecec09193b0cef559c3` |

## What this receipt does not claim

It does not claim the Edit Contract is reached by production. The `modelo.edit.apply`
operation is enrolled, carries scalar, binding and detail-row intents, and resolves a
typed workspace refresh target, but nothing under `entrypoints/` submits it. Wiring that
submission is a later concern and is deliberately outside this receipt. A reader should
take this as certifying that the contract is correct and composable, not that an
operator can invoke it today.

The `NOT_APPLICABLE` arm of the proof schema remains available and is deliberately
unused here. It is the only honest shape for an unmeasured dependency, and retaining it
means a later withdrawal of either predecessor falls back to it rather than the field
silently disappearing.
