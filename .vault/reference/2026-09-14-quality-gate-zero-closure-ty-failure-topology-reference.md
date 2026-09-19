---
tags:
  - '#reference'
  - '#quality-gate-zero-closure'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:bbbddbd0804280647d60b7cbed981b8c4bb5d8f4f708442e0749e3ff5608cd36'
related:
  - "[[2026-08-24-quality-gate-zero-closure-adr]]"
  - "[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]"
  - "[[2026-09-08-quality-gate-zero-closure-product-boundary-adr]]"
---
# `quality-gate-zero-closure` reference: `ty failure topology`

This reference records a static analysis of the live type-check output and the source contracts that produce its dominant patterns. It is a revision-scoped observation, not a diagnostic baseline or an implementation plan.

## Summary

The canonical gate is `just check-types`, which invokes `uv run --no-sync python -m dev.quality.types` at `justfile:218-223`. Its first live run exited 1 with 11,972 diagnostics: 11,094 from ty, 225 from pyrefly, and 653 from BasedPyright. The wrapper and ty target set are defined at `dev/quality/types.py:53`, `dev/quality/types.py:173`, and `dev/quality/types.py:307`; all ty rules are errors and unresolved imports have no allowance at `pyproject.toml:972-987`. ty is lock-pinned to 0.0.77 at `uv.lock:4364-4365`. Its direct invocation returned exit 1, valid uncapped GitLab JSON of approximately 6.04 MB, and empty stderr. `just audit-types` prints full detail but is deliberately advisory and exits 0 at `justfile:1062-1065`; it is not the blocking verdict.

A ty-only measurement at 2026-09-14T13:24:50Z observed commit `c50b9a6d3981946a93ff7a6dbd2d3e4148adb8b6`, 107 dirty paths, 11,116 diagnostics, and 1,162 affected files. Adjacent measurements moved from 11,094 to 11,129 to 11,116, and an independent audit then observed 11,114, while commit identity stayed fixed. These totals describe concurrent worktree state only and must not become a threshold, ratchet, or backlog authority.

The dependable signal is concentrated. In the anchored snapshot, the four leading rules account for 10,381 of 11,116 diagnostics (93.4%): 4,469 `unresolved-attribute`, 2,588 `missing-argument`, 1,893 `unknown-argument`, and 1,431 `invalid-argument-type`. Tests carry 10,333 diagnostics (93.0%); production and admitted development tooling carry 783 (7.0%). The smaller independent-checker populations over their production subsets support treating stale high-fanout consumers as the dominant topology without dismissing the production residue.

## Verified root-cause families

### Registry-projected token consumers still use retired enum-member syntax

The 4,469 `unresolved-attribute` findings span 537 files. The leading owners are `IvaCategory` (733), `IvaTerritorialScope` (348), `SpendingCategory` (304), `IvaRateKind` (293), `EUMemberState` (243), `IvaRate` (219), `IVARegime` (197), `IvaFlowDirection` (182), `ProrrataRegisterRegime` (161), and `IvaDeductionFactKind` (111). Those ten names alone produce 2,791 diagnostics.

This is a verified contract mismatch, not an inference from checker wording. `IvaCategory`, `EUMemberState`, and `IvaRateKind` are opaque string tokens with no class members at `src/cadrumo/domain/iva/schema.py:61`, `src/cadrumo/domain/iva/schema.py:250`, and `src/cadrumo/domain/iva/schema.py:324`. The same shape is visible for `IvaTerritorialScope` at `src/cadrumo/domain/iva/classification.py:129`, `IvaRate` at `src/cadrumo/domain/invoices/enums.py:39`, `IVARegime` at `src/cadrumo/domain/deadlines/models.py:51`, `IvaFlowDirection` at `src/cadrumo/domain/iva/flow.py:100`, and `ProrrataRegisterRegime` at `src/cadrumo/core/prorrata_register.py:16`. Consumers still contain expressions such as `IvaCategory.DOMESTIC_REVERSE_CHARGE`; for example `src/cadrumo/adapters/persistence/profile/tests/test_evidence_confirm_iva_category.py:96-99`.

Future repair must obtain these values through the owning typed registry catalogue and active authority context. Reintroducing enum members, hard-coded token constants, direct unvalidated construction, facades, or ignores would contradict the registry-authority and no-legacy contracts.

### Ports-bundle migrations left high-fanout callers on displaced keywords

`missing-argument` plus `unknown-argument` contributes 4,481 diagnostics. A high-confidence subset of 1,735 is concentrated in five callees: `calculate_modelo_revision` (490), `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics` (450), `create_work_unit` (354), `create_manual_transaction` (260), and `verify_modelo_revision` (181). The paired shape is causal: the same call family reports old repository keywords as unknown and the new `ports` parameter as missing.

The current public signatures require `CalculationActionPorts`, `WorkLifecyclePorts`, or `LedgerActionPorts` at `src/cadrumo/application/modelo/calculation_actions.py:222`, `src/cadrumo/application/modelo/calculation_actions.py:1321`, `src/cadrumo/application/modelo/work_lifecycle.py:319`, and `src/cadrumo/application/ledger/actions_manual.py:114`. The bundle definitions are at `src/cadrumo/application/modelo/calculation_action_ports.py:79`, `src/cadrumo/application/modelo/work_lifecycle_ports.py:20`, and `src/cadrumo/application/ledger/action_ports.py:25`. Repository history ties this fan-out to the 2026-09-14 application-boundary centralisation change, while many tests and secondary consumers still pass individual repository parameters.

Repair should migrate each caller through its established composition or test-support bundle. Restoring optional repository keywords or compatibility wrappers would recreate the displaced boundary and violate the accepted direct-canonical contract.

### One broad test-helper annotation expands into 936 false multiplicities

Of 1,431 `invalid-argument-type` findings, 936 name `confirm_invoice_draft_from_evidence`. They arise from only 34 call sites in 13 files. The common helper `invoice_confirmation_kwargs` is annotated as `Mapping[str, object]` at `src/cadrumo/adapters/persistence/profile/tests/_invoice_confirmation_test_support.py:295`; callers expand it with `**`, including `src/cadrumo/adapters/persistence/profile/tests/test_evidence_confirm_iva_category.py:76`.

Because an arbitrary string key from that mapping could bind any keyword-only parameter, ty compares `object` with nearly every parameter type at each expansion. A single invocation can therefore emit 28 or 29 diagnostics. This is a genuine helper-contract defect but a diagnostic cascade: it is not evidence of 936 distinct application defects. The repair boundary is a closed typed keyword shape or an explicitly typed invocation helper, preserving the real confirmation path.

### Required authority and provenance contexts are missing at older callers

A separate part of the `missing-argument` population reflects newly explicit authority rather than ports bundling. A contemporaneous sample contained 212 omissions of `schema_id` and `schema_version`, 51 missing `operation` at `territorial_scope_for_country`, 43 missing `rate_provider`, 32 missing `profile_decode_context`, 27 missing country-code `operation`, and 26 missing `ports`, `operation`, and `legends` at draft extraction. These are contract migrations. They must be resolved by threading the owning typed authority/context through the call chain, not by defaulting, global lookup, or making filing-grade provenance optional.

## Independent residue

After the dominant families, the main populations are 279 `missing-override-decorator`, 151 `unsound-return-statement`, 73 `not-iterable`, 40 `unresolved-import`, 36 `unresolved-reference`, 33 `not-subscriptable`, 24 `invalid-return-type`, and 23 `unsound-assignment` diagnostics. These should not be bulk-labelled as cascades.

The override family is mechanically uniform but distributed over real protocol and visitor implementations. Return and assignment findings often expose `Any` or `Unknown` crossing a typed boundary and need source-local review after upstream import and call-signature repairs. The unresolved imports include retired module members and incorrect relative depth; they are high-confidence defects individually. Production-heavy files include `src/cadrumo/entrypoints/live_state_composition.py`, `dev/registry/facts.py`, `dev/quality/import_health.py`, `dev/registry/bindings.py`, and `src/cadrumo/entrypoints/adapter_composition.py`. Concrete independent signals include raw-object subscripting in `dev/quality/import_health.py:63-94`, optional AST values crossing required AST boundaries in `dev/registry/facts.py:1635`, and incompatible projected-token return types in `src/cadrumo/domain/calculations/registry/prorrata_register_catalogue.py:119-143`.

## Dependable measurement protocol

A future remediation batch should record the timestamp, full commit identity, ty version, exact target tuple, and complete dirty-path ledger; parse ty's GitLab JSON directly; and group findings by boundary, rule, producer class, callee, and call site. Counts and worst-file rankings are routing hints only. The raw JSON is the analysis source; `just check-types` remains the blocking verdict, and the exit-0 audit formatter must never substitute for it.

Prioritise producer contracts in this order: migrate callers to typed ports bundles; migrate retired enum-member consumers through canonical registry projections; repair the broad confirmation helper type; thread required authority/provenance contexts; then remeasure the independent production residue. After each owner-scoped batch, rerun ty and the independent production checkers so a local count reduction cannot hide a cross-checker regression.

A stable green claim requires a clean pinned snapshot. In this shared worktree, repeated totals are expected to move and cannot ground completion. The accepted quality-gate record also states that its prior rolling type controller has no installation vehicle, while the live plan is repurposed to import-quality work. This reference therefore authorizes diagnosis only; implementation needs current path ownership and an approved ADR/plan rather than attachment to the historical count.
