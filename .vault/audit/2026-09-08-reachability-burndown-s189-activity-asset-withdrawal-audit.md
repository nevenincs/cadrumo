---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:2bf5467f109d112716b91c801b3d056d127741c2fbfbb2306dc3398b7035e716'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S189]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
---

# `reachability-burndown` audit: `S189 activity asset withdrawal review`

## Scope

Independent review of `W05.P12.S189` against the complete reachability plan, its accepted ADR and reference, the amortization grounding research, the amended amortization decision, the Step Record, the live diff, and the current source tree. The review traced the withdrawn scalar activity-asset records and repositories through storage namespace enrollment, error registration, locales, shared persistence fixtures, and generated API stubs, then exercised the distinct finca and bienes-inversión slices.

The scalar implementation itself was test-only before withdrawal: repository and record consumers were confined to self-tests, shared persistence conformance fixtures, generated documentation, and the source-connectivity census; no application acquisition, calculation resolver, registry binding, or filing producer consumed it. Current-tree searches confirm the defining modules, repositories, namespaces, error registrations, activity-asset API stubs, and dedicated self-tests are absent.

Focused evidence: 31 finca and bienes-inversión tests passed; the API-stub gate passed 2 tests; Ruff passed for the reviewed S189 Python paths. A broader 100-test persistence run produced 94 passes and six failures. Those six are peer-owned current-tree drift: five namespaces missing from the registry, three declarations for modules that no longer resolve the active bucket, and four unrelated workflow/calculation/borrador schema changes. None names the withdrawn activity-asset slice. The locale audit is also red only on peer-owned declaration-workspace, cotejo, and source-mesh keys; it reports no activity-asset locale residue.

## Findings

### activity-asset-withdrawal | high | Shipped bienes-inversión surfaces still name or reinterpret the withdrawn AssetRecord contract

The removal is not end-to-end at the product vocabulary boundary. All four shipped CLI locale files still describe `--asset-ref` as an `AssetRecord` identifier, and `adapters.persistence.profile.bienes_inversion` still links to the deleted `adapters.persistence.profile.assets` module as the sibling shape it mirrors. More importantly, `BienInversionIvaRecord.asset_record_ref` was retained and its domain documentation changed from a cross-reference to the deleted `AssetRecord` into an opaque reference “reserved for a validated activity-asset schedule.” That is a reinterpretation of the existing scalar-reference payload for a future replacement, while the amended ADR explicitly says a future replacement must not reinterpret payloads from the withdrawn scalar representation. Preserving bienes-inversión behavior does not require shipped help or docs to promise the deleted type, and the governing decisions must explicitly reconcile whether this existing field is an independent bienes-inversión contract or forbidden compatibility residue. Closure is withheld until the contradiction is resolved through the owner.

### runtime-coverage-proof | medium | The active-bucket coverage declaration still claims a removed profile_assets refusal case

`test_active_bucket_consumer_coverage.py` maps the generic `_secure_model_document.py` consumer to the case name `profile_assets`, but S189 removed that case from `_RUNTIME_DEFAULT_REFUSAL_CASES`. The gate validates only module keys, not that the named case exists, so it remains capable of claiming coverage through a nonexistent witness. This is not a new S189 metastate list, but S189 made an existing hand-maintained proof stale while modifying the owning refusal table. The reachability ADR already rejects maintained module-name coverage lists; at minimum, this false witness must not be cited as S189 verification.

### step-record-scope | high | The S189 Step Record attributes extensive peer-owned changes to this step

The Step Record’s `Changes` section is not an auditable account of S189. It lists dozens of unrelated API-stub deletions and additions, unrelated locale formatting/removals, and even a nonexistent `ocs/api/cadrumo.adapters.outbound.aeat.sede.deudas.rst` path. These entries came from the shared dirty worktree rather than the S189 slice. The record also stores the focused pytest command as an unspecified bracketed description and records failing gates without their exact peer-owned diagnostics. Consequently the plan and ADR describe a narrow activity-asset withdrawal while the record claims a much broader deletion campaign. Closure evidence is not reliable until the record is reduced to exact S189-owned changes and exact commands/results.

### activity-asset-withdrawal-resolution | low | Prior shipped-vocabulary blocker resolved

Re-review confirms that `asset_record_ref`, `--asset-ref`, `asset_ref_help`, `AssetRecord`, the deleted asset module paths, their namespaces, and their storage names no longer occur in shipped source or generated API stubs. `acquisition_ledger_id` remains required from CLI through application and domain persistence, is uniqueness-validated, and is checked reciprocally against the acquisition observation. The amended bienes-inversión decision now names it as the sole live link. The original activity-asset-withdrawal finding is resolved.

### runtime-coverage-proof-resolution | low | Prior hand-maintained census blocker resolved

The entire `test_active_bucket_consumer_coverage.py` coverage-disposition census was deleted. No replacement identity list, threshold, baseline, or exception inventory was introduced. The original runtime-coverage-proof finding is resolved.

### step-record-scope-resolution | low | Prior dirty-tree attribution blocker resolved

The regenerated record now attributes only the activity-asset withdrawal, bienes-inversión cross-reference removal, governing ADR amendments, directly owned locale/API paths, and deletion of the exposed census. It explicitly excludes unrelated API scaffold churn. The original broad dirty-tree attribution finding is resolved, subject to the separate verification-accuracy finding below.

### step-record-verification | high | Recorded passing Vault commands are invalid and focused behavioral proof is omitted

The Step Record says `uv run --no-sync vaultspec-core vault check --feature amortization-casilla-mapping` and the analogous bienes-inversión command passed. Running that exact syntax exits 1 because `vault check` has no `--feature` option. The record therefore claims successful evidence from commands that cannot run. It also records no exact focused pytest command for the retained finca and bienes-inversión behavior, despite that being an explicit S189 requirement. Independent re-review supplied that missing evidence—70 selected tests passed and 18 integration-marked tests were deselected—but reviewer evidence does not repair an inaccurate Step Record. Closure remains withheld until the record uses the actual owning Vault invocation and records the exact focused behavioral command/result.

### bienes-inversion-adr-status | medium | The amended accepted ADR still ends by declaring itself proposed

The ADR title declares status `accepted`, while its final `## Status` section says `proposed`. This internal lifecycle contradiction survived the amendment and makes the owner decision ambiguous in the same artifact used to authorise removal of the public field. Vault checks currently accept the title status and do not detect the contradictory prose. The ADR must carry one status before it can serve as unambiguous S189 authority.

### step-record-verification-resolution | low | Corrected Step Record now cites executable verification evidence

The Step Record now records the actual successful `mcp__vaultspec_core__check` calls for both governing features and includes the exact focused pytest command. The previously invalid CLI claims are gone. The reviewer repeated both feature checks: each reports zero errors and zero warnings. The step-record-verification finding is resolved.

### bienes-inversion-adr-status-resolution | low | Accepted status is internally consistent

The bienes-inversión ADR now declares `accepted` both in its title and in its final Status section. Its constraints, implementation, and consequences consistently establish `acquisition_ledger_id` as the sole live acquisition link and reject reconstruction of the withdrawn activity-asset surface. The bienes-inversion-adr-status finding is resolved.

### final-disposition | low | Approved with no open S189 findings

All previously logged findings are resolved. Final narrow residue search finds no `asset_record_ref`, CLI option/help key, deleted `AssetRecord` or asset-module reference, asset namespace symbol, or `profile_assets` census residue in shipped source or generated API stubs. The production implementation, governing ADRs, plan row, and Step Record agree. Independent review approves closing `W05.P12.S189`; the standing exact unused-symbol and orphan-test reds remain campaign signals, not S189 regressions.

## Recommendations

Approve `W05.P12.S189` for closure. No S189 remediation remains.

Continue the campaign from the live exact signal recorded by the Step Record: 341 unused symbols and 18 orphan test modules. Preserve the peer-owned locale red classification and do not absorb it into this step.
