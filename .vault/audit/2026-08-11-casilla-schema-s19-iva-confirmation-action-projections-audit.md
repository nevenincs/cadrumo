---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:b7add4f0ef2a3db71705349b20ab82657b9bd7fe0811b1058179a7252eed7b8c'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S19 IVA and confirmation action projections`

## Scope

Reviewed W02.P06.S19 against the accepted blocker-spine decision, campaign plan, research, and repository quality constraints. Scope was limited to the IVA ledger preflight owner and facade, the existing real IVA issue tests, the core confirmation-gate owner and facade, and the new confirmation projection test. The required contract is two immutable, exact-set, import-refused projections from the complete native reason vocabularies to `OperatorActionAxis`, retained beside their native facts, with direct facade identity and no compatibility or duplicate authority.

## Findings

### s19-iva-confirmation-action-projections | medium | outside-period rows are misclassified as prior-period filing work

`OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE` maps `IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD` to `FILE_PRIOR_PERIOD`. The native reason only says that a transaction date is outside the selected period; it is emitted for both sides of the filing window, including future-dated catalogue rows, and the full-catalogue IVA aggregation deliberately reports every out-of-window row from its plaintext date index. The canonical modelo-binding consumer suppresses `OUTSIDE_PERIOD` together with `PERSONAL_TRANSACTION` because these are normal exclusions rather than readiness blockers for the selected filing. Consequently `FILE_PRIOR_PERIOD` invents a direction the native fact does not contain and can tell an operator to file a prior period for a future row or for an ordinary irrelevant catalogue entry. The projection must use an action truthful for a non-blocking/out-of-window exclusion, or the action vocabulary must be extended if none is adequate; the native reason/detail must remain beside it.

### s19-iva-confirmation-action-projections | medium | ledger facade omits static ownership for the new lazy export

The ledger facade adds `OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE` to `_LAZY_EXPORTS` and `__all__`, so runtime facade access resolves to the owning `_preflight` identity and returns all 22 entries. It does not add the symbol to the facade's corresponding `TYPE_CHECKING` import from `_preflight`. Strict BasedPyright on the required facade therefore reports `reportUnsupportedDunderAll`: the name is specified in `__all__` but is not present in the module. Add the canonical type-only import using the facade's existing lazy-export pattern; do not replace laziness or introduce a second declaration.

The remainder of the implementation passed review. The IVA mapping is owned beside the native `IvaLedgerAggregationIssueReason`, wrapped in `MappingProxyType`, exported by the application-ledger facade at runtime, and guarded by exact key-set equality that reports both missing and stale keys. The other 21 mappings consistently separate missing ledger substrate, value/category contradictions, rate-table revision coverage, evidence requirements, identity defects, and advisory exclusions into typed action classes without replacing the native issue or detail.

`OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON` is owned directly beside the five-member core `ConfirmationBlockReason`, immutable, exact-set guarded at import, and directly imported/exported by the core facade. Closure and regime contradictions map to value-divergence resolution, ambiguous identity maps to identity resolution, and unresolved direction or establishment map to manual supply. These actions agree with the native reason documentation and no native confirmation fact is removed.

The tests import production enums, facades, owners, and mappings. The IVA module retains its real screen-emission census and totality/property checks; the checked-in enum mutation/module-copy harness has been removed, complying with the repository prohibition on monkeypatched mutations. The new core test proves public identity, totality, typed values, and representative semantics. No fake, stub, mock, patch, monkeypatch, skip, expected-failure, shadow enum, or copied projection algorithm remains.

## Verification

- Fresh semantic discovery located both native owners, projection tables, direct tests, public routes, and the accepted blocker-spine decision before exact inspection.
- Focused S19 tests: 5 passed.
- Scoped Ruff: passed.
- Scoped strict BasedPyright: one new ledger-facade `reportUnsupportedDunderAll` error; all other reviewed files passed.
- Scoped `git diff --check`: passed, with only line-ending warnings on existing working-copy files.
- Runtime ledger facade identity: passed; projection has 22 typed entries.
- Core facade identity and exact five-member coverage: passed.
- Exact totality guards: both compare projection keys to their complete native enum and report missing plus stale keys before normal module use.
- Exact symbol inspection: one owner declaration per projection and one facade route; no aliases or duplicate mapping authority.
- Prohibited test-construct scan: no hits after removal of the legacy enum-mutation harness.

## Recommendations

Resolve both medium findings before closing S19. Reclassify `OUTSIDE_PERIOD` without inferring that every out-of-window row belongs to a prior filing, and add a direct regression that covers a future-dated or otherwise non-prior row so the semantic boundary is executable. Add the missing `_preflight` symbol to the ledger facade's existing `TYPE_CHECKING` import and rerun strict BasedPyright on the facade itself as well as the owner. Preserve the exact-set import guards, lazy runtime identity, and all native reason/detail facts.

Verdict: **CHANGES REQUESTED.** Both canonical projections, exact totality guards, core facade, and real tests are structurally sound, but S19 currently publishes one semantically false action and one statically incomplete public ledger export.
## Re-review resolution status

### s19-iva-confirmation-action-projections | resolved medium | ledger facade now declares static lazy-export ownership

The ledger facade now imports `OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE` from `_preflight` inside its existing `TYPE_CHECKING` block while retaining the same `_LAZY_EXPORTS` runtime route and `__all__` entry. Runtime access still resolves to the canonical owner identity, and strict BasedPyright over the facade and scoped owners/tests now reports 0 errors, 0 warnings, and 0 notes. The static-ownership finding is resolved without eager-loading the package or introducing a second declaration.

### s19-iva-confirmation-action-projections | medium remains open | outside-period still invents corrective work

Changing `OUTSIDE_PERIOD` from `FILE_PRIOR_PERIOD` to `IMPORT_LEDGER_DATA` removes the false prior-direction inference but does not resolve the underlying semantic finding. The new real regression constructs a valid transaction dated 2026-07-02, evaluates it against Q2 2026, and correctly proves that the production aggregation emits native `OUTSIDE_PERIOD`. Nothing in that behavior proves the row or its imported data is defective: it may simply be a valid Q3 row present in the deliberately full catalogue. The test then looks up the production table and asserts `IMPORT_LEDGER_DATA`, while its name declares that the row "requires ledger data repair"; that corrective premise is not supported by any native fact or producer behavior.

The canonical consumer still suppresses `OUTSIDE_PERIOD` as a normal exclusion, and the native reason remains directionless and correctness-neutral. Therefore `IMPORT_LEDGER_DATA` continues to tell an operator to change or re-import data that may already be correct. Use the non-blocking action consistent with a normal exclusion, such as `REVIEW_ADVISORY`, or extend the action axis if architecture requires a more precise no-current-filing-action class. Strengthen the test name and expectation to preserve the real future-row bite without asserting an unsupported repair premise.

Re-review verification: 6 focused tests passed; scoped Ruff passed; strict BasedPyright including the ledger facade reported 0 errors, 0 warnings, and 0 notes; scoped `git diff --check` passed with line-ending warnings only.

Final re-review verdict: **CHANGES REQUESTED.** One of two medium findings is resolved. The static facade is now correct, but `OUTSIDE_PERIOD -> IMPORT_LEDGER_DATA` remains semantically untruthful for the real valid future-row case the new regression demonstrates.
## Final resolution review

### s19-iva-confirmation-action-projections | resolved medium | outside-period is now a nonblocking advisory

`IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD` now projects to `OperatorActionAxis.REVIEW_ADVISORY`. This matches the canonical consumer's normal suppression of out-of-window catalogue rows, retains the native directionless reason/detail, and makes no unsupported claim that a valid earlier or future row requires filing or data repair. The real regression is now named `test_future_out_of_window_row_is_a_nonblocking_review_advisory`; it constructs a valid 2026-07-02 transaction against Q2 2026, proves production aggregation emits native `OUTSIDE_PERIOD`, and proves the public production projection yields `REVIEW_ADVISORY`. The remaining semantic finding is resolved.

The previously resolved ledger-facade `TYPE_CHECKING` import remains present and strict static ownership remains green. Final independent verification passed 6 focused tests, scoped Ruff, strict BasedPyright with 0 errors, 0 warnings, and 0 notes, and scoped `git diff --check`.

Final verdict: **PASS.** Both medium findings are resolved. W02.P06.S19 now publishes two canonically owned, immutable, exact-set import-refused projections with truthful actions, direct public identities, preserved native reasons, and real tests without mutation harnesses, doubles, mirrors, or compatibility paths.
