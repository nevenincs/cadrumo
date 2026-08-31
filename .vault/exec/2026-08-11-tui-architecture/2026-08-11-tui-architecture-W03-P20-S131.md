---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:4e98920a8fa04ca2b8dec1c293604c419a90084c729b77800344563039ac6ab9'
step_id: 'S131'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Implement the sole ModeloWorkspaceC2DependencyReceiptV1 validator with current-HEAD, accepted-authority, closed-predecessor, public-schema, native-owner surface inventory, native/S126 seam-conformance digest, producer inventory, field denominator, process-incarnation refusal, conformance, no-legacy, and semantic redeclaration evidence checks while leaving receipt minting to the C1 handoff phase

## Scope

- `src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py`

## Changes

- `A` `src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py -m unit -q -n0` -> `pass` (9 passed)
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py` -> `pass`

## Notes

Mirrors the C3 sibling (`test_edit_dependency_receipt.py`, ADR decision D8)
exactly: the receipt schema, its predecessor tuple, and its validator are
all defined INSIDE this test module, never in a separate production module,
because minting the durable `.vault/reference/...c2-dependency-receipt.md`
artifact is deferred to the C1 handoff phase per this Step's own scope --
S131 builds and proves the schema and validator only.

`ModeloWorkspaceC2PredecessorTupleV1` models the ADR's closed, ordered
five-entry predecessor set as FIVE NAMED FIELDS (`gate_adr`, `interface_adr`,
`c1_exit_receipt`, `authority_grade_decision`, `native_owner_inventory`)
rather than a generic list: reordering is structurally impossible, and a
missing predecessor is a missing required pydantic field rather than a
shorter list a count-based check could silently accept.

One interpretive decision, recorded rather than guessed silently: the ADR's
predecessor #4, "the accepted or formally reconciled authority-grade
decision", names no dedicated ADR stem anywhere in the tracked tree (checked:
no `.vault/adr/*authority-grade*` document governs the `RegistryAuthorityGrade`
admission dispatch this same ADR itself defines). Read it as reconciled
INSIDE the same accepted `2026-08-24-tui-registry-api-gate-adr.md` via its
own "Amendment (S287)" section, with
`2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md`
(dated the same day) as the reconciliation artifact. `authority_grade_decision_proof`
is `PASSED` on that reading.

Every denominator-shaped proof gates on a PROPERTY read from the live
registration, never a literal count, per direction: `native_owner_surface_inventory_proof`
asserts `{contract.contributor_kind for contract in ...} == set(ModeloWorkspaceContributorKindV1)`,
so a legitimate ninth contributor changes the SET being compared, not a
hardcoded tally someone has to remember to bump.

Found and fixed one real bug before landing, the SAME false-positive class
this session already hit twice today (S129's `_workspace.py` suffix match,
S130's `"ModeloWorkspace"` substring match): the first `no_legacy_proof`
draft used a raw substring scan for `legacy`/`migrate`/`upgrade`/`deprecated`
over whole file text, which false-positived on `workspace.py`'s own
docstring ("the *legacy* single-read call sites", describing OTHER code)
and `workspace_models.py`'s ("Retired outright rather than migrated", a
negation). Replaced with `_assert_no_legacy_identifier`, an AST walk that
checks only CODE IDENTIFIERS -- function/class names, argument names,
`ast.Name` references, and import aliases -- never docstrings, comments, or
string literals. The pattern is now explicit across three Steps in one
session: a gate that greps for a name catches the code defending against
that name.

`redeclaration_proof` reuses the same AST-walk technique S130 built
(`test_no_domain_or_adapter_module_imports_any_modelo_workspace_symbol`'s
sibling logic) scoped to `application/modelo` itself, asserting each of four
canonical entry points (`resolve_static_inspection_result`,
`resolve_graded_snapshot_result`, `ModeloWorkspaceProjectionV1`,
`ModeloWorkspaceRegistryPortV1`) is defined in exactly one module.

This module's first draft landed via a peer's shared-index commit
(`67467b10bb`) already carrying the final, fixed version -- confirmed via
`git diff 67467b10bb` against the working tree showing zero remaining
difference, so no separate follow-up commit was needed for this Step.
