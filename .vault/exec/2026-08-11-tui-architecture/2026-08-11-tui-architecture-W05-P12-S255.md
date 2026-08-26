---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f4ec90e6ec5819153d1893a90557aae6d3bfedb98c0ba098baffbc10f1e2680e'
step_id: 'S255'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Build the generic operation result-projection mechanism symmetric with REVIEW's reviewed_operand_type and review_projector, so a settled operation can expose a typed PUBLIC result distinct from its private result_type: add a result_projector slot and its registry validation, a projection service resolving result_ref to the stored operand and through the projector to a public schema instance, its frontend request success and refusal contracts, and its OperationComposedServices slot, covering the refused and failed settlement paths as well as succeeded, and amend the operation-observation decision record in the same change; no operation binds its private result_type as its own public schema

## Scope

- `src/cadrumo/application/operations/registry.py`
- `projection_services.py`
- `frontend_contracts.py`
- `composition.py`
- `the amended operation-observation ADR`
- `and focused result-projection contract tests`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

- `M` `src/cadrumo/application/operations/registry.py`
- `M` `src/cadrumo/application/operations/projection_services.py`
- `M` `src/cadrumo/application/operations/frontend_contracts.py`
- `M` `src/cadrumo/application/operations/composition.py`
- `M` `src/cadrumo/entrypoints/tests/test_operation_composition.py`
- `M` `src/cadrumo/application/operations/tests/test_registry.py`
- `M` `.vault/adr/2026-08-11-tui-architecture-adr.md`
- `verify:` `pytest src/cadrumo/application/operations/ -m integration` -> `pass` (pre-existing unrelated failures only: test_supervisor_recovery.py races, environment-only auth.provider.configure keyring case)
- `verify:` `pytest src/cadrumo/application/operations/tests/test_registry.py -m unit` -> `pass` (47 passed)

## Notes

The decision record amended is `.vault/adr/2026-08-11-tui-architecture-adr.md`
(D6), not a separate "operation-observation" ADR: the C0 receipt confirms
this is the sole currently accepted governing record for the operations
package (the sibling `2026-08-24-tui-operation-observation-adr.md` is a
retired staging record whose clauses were already copied into this same
parent and is permanently `rejected`). D6 gained a new paragraph describing
`result_projector`, `OperationResultProjectionService`, and its refusal
codes, symmetric with the existing REVIEW paragraph.