---
tags:
  - '#audit'
  - '#cpdefix-followup-allgreen'
date: '2026-07-05'
modified: '2026-07-08'
related:
  - "[[2026-07-05-cpdefix-followup-allgreen-plan]]"
---

# `cpdefix-followup-allgreen` audit: `current blocker resync`

## Scope

Resynced the cpdefix follow-up campaign after the shared worktree advanced past the previous blocker inventory. The review covered the older cpdefix calculation checkpoint, the persona closeout ledger, the binding-resolver closeout audits, the accepted counterpart-source provider ADR, the current Modelo 720 row-carrier plan and audit, the current M347 registry binding slice, and the source-mesh disposition code.

Discovery used `vaultspec-rag` for vault and code searches before grep confirmation. Verification used focused pytest gates for M720 row carrier, foreign-asset enrollment, M347 registry/counterpart behavior, source-enrollment health, and import hygiene.

## Findings

### counterpart-provider-promotion-remains-gated | medium | reserved provider enrollment is not code-ready

The accepted counterpart-source provider ADR still governs the reserved `ledger_transaction` and `purchase_invoice_evidence` sources. It requires provider enrollment to co-land with the first registry revision that declares one of those reserved sources. Current M347 summary bindings do not declare those sources, so enrolling `CounterpartAggregationSourceResolver` now would contradict the ADR and risk a silent empty live-path resolution. Future code-fixer briefs must not promote the provider unless that trigger is explicitly approved and the registry/provider/test changes co-land.

### m347-no-bindings-blocker-is-stale-in-part | medium | M347 now has invoice-owned summary bindings

The old blocker that M347 had no declaring bindings is stale. The current registry has committed M347 summary bindings and `src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py` proves the invoice-total threshold behavior. This does not fire the counterpart-provider trigger because the bindings are intentionally invoice-owned (`collectible_invoice` / `payable_invoice`), and the counterpart tests assert the reserved provider does not claim them. Verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/domain/calculations/registry/tests/test_modelo_347_registry_bindings.py src/aeat/application/aggregation/tests/test_per_modelo_service.py -k "counterpart" --tb=short` reported 4 passed and 23 deselected.

### m720-row-carrier-blocker-is-stale | low | foreign_asset row carrier and enrollment have landed

The older binding-resolver closeout statement that M720 still lacked a row-indexed carrier is stale. Current source has `CalculationSourceResolution.row_binding_values`, the foreign-assets resolver returns validated row binding values through that carrier, and the calculate path enrolls `ForeignAssetsAggregationSourceResolver`. Verification passed: `uv run --no-sync pytest -q -n 0 src/aeat/application/aggregation/tests/test_foreign_assets.py src/aeat/application/modelo/tests/test_calculation_resolution.py src/aeat/application/modelo/tests/test_revision_replay_inputs.py src/aeat/application/aggregation/tests/test_source_mesh.py src/aeat/application/aggregation/tests/test_source_mesh_readiness.py --tb=short` reported 62 passed.

### source-enrollment-health-current | low | prior global source-enrollment blocker is stale

The earlier global source-enrollment concern tied to Modelo 145 is no longer a blocker at current HEAD. Focused gates passed for M145 source catalogue/foundation/support matrix, aggregation source enrollment/status, and source-mesh missing-source checks. The current live source partition still keeps only the detail-row deferrals plus the reserved counterpart headroom.

### import-hygiene-gate-fixed | low | one live regression was already repaired

The resync found one real current failure: the import-hygiene gate rejected undocumented private test imports. That was fixed in commit `07edea5a68` before this tracker was scaffolded. Verification passed for the import-hygiene gate (11 passed), the touched test files (39 passed, 41 deselected), the two harder public-behavior replacements (31 passed), ruff on the touched files, and diff whitespace checks.

### shared-worktree-risk | medium | concurrent campaigns require own-path discipline

The working tree remains heavily dirty from other concurrent campaigns, though the index was empty at this resync point. Future dispatches must inspect `git diff -- <file>` before editing, avoid any destructive git operation, stage exact owned paths only, and close completed agents promptly so slots stay free.

### closeout-review-clean | low | final diff has no additional blocker

The closeout review covered the final plan state, the cpdefix vault artifacts, and the only source edit in `src/aeat/domain/calculations/registry/_validate_verification_predicates.py`. The source edit only compresses module docstring prose, leaves the reviewability baseline unchanged, and is covered by the targeted reviewability test plus the S09 scoped aggregation/registry gate. No critical, high, or medium issues were found in the final diff.

## Recommendations

- Execute Wave W01 before further coding: keep the blocker inventory and testimonial ledger current against HEAD.
- Treat M720 row-carrier and `foreign_asset` enrollment as closed unless a fresh focused gate fails.
- Treat M347 invoice-owned summary as current product behavior; do not promote the reserved counterpart provider without the ADR trigger.
- Continue with the deferred/reserved source partition audit before selecting another calculation-hardening code task.
- Every future code fixer brief must require `vaultspec-rag search "<task terms>" --type code` before editing, then grep confirmation, no reexports/shims unless the owning public surface is already real, and no destructive git commands.
