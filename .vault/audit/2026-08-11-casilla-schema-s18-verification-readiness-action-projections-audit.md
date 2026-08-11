---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:0a44727e2a8354ddc3d0d3945310990adc47c2bad52578f23bebd7a34aabb30c'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S18 verification and readiness action projections`

## Scope

Reviewed W02.P06.S18 against the accepted blocker-spine decision, campaign plan, research, and repository quality constraints. Scope was limited to the verification finding projection and domain facade, readiness state projection and readiness builder, readiness payload/CLI assembly, the two new direct test modules, and the one-line quickfile fixture correction. The required contract is total import-refused action projection for all native finding/source/reason vocabularies, typed readiness payload actions carried beside every native selector/source/reason fact, strict canonical source hydration, and no compatibility or duplicate vocabulary.

## Findings

### s18-verification-readiness-action-projections | medium | non-ledger sources direct operators to import ledger data

`OPERATOR_ACTION_BY_MODELO_READINESS_BINDING_SOURCE` maps six canonical source kinds to `IMPORT_LEDGER_DATA` even though their owning source authority identifies them as dedicated non-ledger stores or detail-record sources: `RETENCIONES_AGGREGATION`, `WITHHOLDING`, `FOREIGN_ASSET`, `RELATED_PARTY_OPERATION`, `ATRIBUCION_MEMBER`, and `REFUND_OPERATION`. The strongest direct contradiction is the canonical `BindingSourceKind.RETENCIONES_AGGREGATION` documentation, which says it reads the operator-supplied per-perceptor retencion store, is "NOT the bucket ledger", deliberately has no `ledger_` prefix, and is deliberately absent from `LEDGER_BINDING_SOURCE_KINDS`. `WITHHOLDING` and `FOREIGN_ASSET` likewise resolve through their dedicated observation stores, while `RELATED_PARTY_OPERATION` and `REFUND_OPERATION` are currently deferred Sheets-only detail-row producers; `ATRIBUCION_MEMBER` is another detail-row family. Emitting `import_ledger_data` for these missing bindings gives a surface consumer an operator action that cannot satisfy the declared source. The accepted decision requires each spine value to name a distinct operator action and allows adding a missing action class in the same mapping step. Totality and typing do not make a semantically wrong action safe.

All other scoped S18 behavior passed review. `OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND` is facade-exported, immutable, exactly covers all seven native finding kinds, and preserves the native kind and message facts. Its mappings are coherent: missing/unresolved/blocking input maps to manual supply, reconciliation mismatch to value-divergence resolution, cross-period uncleanness to prior-period filing, invalid waiver to re-verification, and advisory to advisory review.

Readiness missing-profile action is the required `SET_PROFILE_FACT`. The ledger-issue projection exactly covers all 16 canonical `LedgerPreflightIssueReason` members and preserves each native reason/detail in the payload. The binding-source and ledger-issue tables are immutable and their shared assertion now refuses both missing and unexpected keys by exact set equality. Supplied bites independently demonstrated missing-row import refusal for the verification advisory and ledger recargo-equivalencia anomaly; restoration returned imports and gates to green.

`ProjectionModeloBindingRequirement.source` is now the closed canonical `BindingSourceKind`; canonical persisted strings hydrate to that enum and an unknown legacy string raises a Pydantic validation error. The deleted string-normalization helper was not replaced with a shim. `_readiness_result` carries `operator_action` beside the original missing selector, binding source/input channel, and ledger reason/detail, so no native fact is dropped. A runtime payload probe confirmed the enum remains typed in the model while serializing to its stable string value.

The new tests import production models, mappings, and payload assembly. They exercise real construction, exact totality, typed action values, representative semantics, native-fact retention, strict source hydration, and the corrected canonical quickfile source fixture. They contain no fake, stub, mock, patch, monkeypatch, skip, expected-failure, or mirrored business implementation.

## Verification

- Fresh semantic discovery located the accepted blocker-spine decision and the native projection owners before exact inspection.
- Focused new domain/CLI tests plus state-projection module: 23 passed.
- Post-hardening CLI projection module: 2 passed independently.
- Exact corrected quickfile node: 1 passed.
- Final consolidated implementation evidence supplied by the owner: 43 passed plus the exact quickfile node passed.
- Scoped Ruff over all nine S18 paths: passed.
- Strict BasedPyright over the changed domain and application modules: 0 errors, 0 warnings, 0 notes.
- CLI BasedPyright retains seven pre-existing diagnostics outside the changed readiness rows; none points at an S18 addition.
- Scoped `git diff --check`: passed, with only the existing quickfile line-ending warning.
- Runtime censuses: 7 verification kinds, 27 binding source kinds, and 16 ledger issue reasons; each table has exact key-set equality and only typed `OperatorActionAxis` values.
- Strict hydration probe: canonical source string accepted as `BindingSourceKind`; unknown source rejected.
- Prohibited test-construct scan: no hits.
- Import-totality bites: deleting one verification row or one ledger-reason row failed clean import naming the missing native member; both were restored and final imports passed.
- Broader integration boundary supplied by the owner: 18 passed and 24 failed; 23 failures arise from unrelated profile fixtures lacking `tax_residence.jurisdiction_scope`, and the one owned stale quickfile source fixture is corrected and green.
- Real console boundary: execution reaches the existing absent-session typed login refusal before readiness payload rendering, so no successful signed-in console claim is made.

## Recommendations

Resolve the medium finding before closing S18. Reclassify the six non-ledger source kinds to operator actions that truthfully describe how their dedicated stores or evidence rows are supplied. If the accepted action axis lacks the necessary distinct action, use the ADR-authorized path to add that action in the same change and strengthen the direct test with representative non-ledger assertions. Preserve the exact-set import refusal and all native payload facts.

Verdict: **CHANGES REQUESTED.** The S18 projection infrastructure, totality enforcement, typing, native-fact preservation, and real tests are sound, but the operator-facing binding-source projection currently directs six non-ledger source failures to an action that cannot satisfy their canonical source contract.
## Resolution review

### s18-verification-readiness-action-projections | resolved medium | non-ledger action projections now follow their real producers

Re-review confirmed that the six source kinds identified above no longer emit `IMPORT_LEDGER_DATA`. `RETENCIONES_AGGREGATION`, `WITHHOLDING`, and `FOREIGN_ASSET` now emit `SUPPLY_MANUAL_INPUT`, matching the typed observations accepted by `app modelo aggregate` and consumed from their dedicated repositories. `ATRIBUCION_MEMBER` now emits `SET_PROFILE_FACT`, matching the resolver's direct read of indexed `attribution_entity_socios.*` profile facts. `RELATED_PARTY_OPERATION` and `REFUND_OPERATION` now emit `CAPTURE_EXTERNAL_EVIDENCE`, matching their canonical deferred, Sheets-pull-only evidence-row disposition. No other projection values or payload fields changed.

The new six-case regression imports the production mapping and canonical enums, asserts the exact operator workflow for each formerly misclassified source, and contains no helper that recreates classification logic. Fresh semantic discovery and exact producer inspection independently corroborated all six expectations. The table remains immutable and exact-set total over all 27 canonical `BindingSourceKind` members; native source and input-channel facts continue to travel beside the added action.

Resolution verification: the focused verification/readiness/state lane passed 29 tests; scoped Ruff passed; scoped strict BasedPyright reported 0 errors, 0 warnings, and 0 notes; scoped `git diff --check` passed; prohibited test-construct inspection remained clean.

Final verdict: **PASS.** The sole medium finding is resolved. W02.P06.S18 now provides total, import-refused, semantically truthful operator actions for verification findings and the complete readiness triple while preserving every native fact and introducing no compatibility or duplicate authority.
