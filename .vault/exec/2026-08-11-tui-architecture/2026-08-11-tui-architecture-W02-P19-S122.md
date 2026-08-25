---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ec6bfd5ea86db4a6de1f236401819b46cc6fbf8129cba616bbc6a5b1b659ac39'
step_id: 'S122'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Export the sole public operation contract family and compose the immutable production registry, observation, REVIEW, refresh, response, cancel, and detach services with real adapters through one import-light entrypoint seam consumed by CLI, MCP, and the later TUI launcher

## Scope

- `src/cadrumo/application/operations/__init__.py and src/cadrumo/entrypoints/_operation_composition.py`

## Provenance

- The prerequisite public-registry, safe-contract, real-adapter, and owner-registration cutover is committed in `0c585b118c`.
- The one entrypoint composition seam and its integration/import-boundary proofs are committed in `865feaaf52`.
- This closure attests those prerequisite commits without rebundling their source. The final documentation-only Step commit records the independent review, updated execution evidence, plan closure, and regenerated feature index.

## Description

- Promoted public definition-registration builders through the auth, user-profile, and live application facades.
- Registered every shipped auth, profile-maintenance, censal REVIEW, and filed-history definition in one deterministic production registry.
- Added the import-light `OperationProductionDependencies` composition with real journal, lease, secure-reference, provenance, supervisor, observation, REVIEW, refresh, cancellation, detach, response-authority, and shutdown wiring.
- Narrowed `cadrumo.application.operations` so frontend consumers cannot import raw events, interactions, snapshots, journals, leases, replay records, response tokens, or bound bearers.
- Established `cadrumo.application.operations.owner` as the canonical definition home for the narrow application-owner executor protocols; the former `_executor.py` module is deleted, all owner consumers import the canonical module directly, and entrypoints are prohibited from importing it.
- Replaced the secret-capable nested bundle-export operation request with a credential-free public request and kept the passphrase solely in one-shot custody.
- Removed the duplicate default-registration construction shape through `compose_request_only`.
- Retargeted persistence and application implementation imports to their canonical owning modules after the facade cut.
- Made active-profile secure references and filed-history sync-run persistence lazy at their canonical adapter and definition seams, so the login-bearing graph composes before any profile session exists and does not retain a stale repository after a profile switch.
- Used semantic discovery before implementation and again after the cut to verify the production composition and registration producer fixed points.

## Outcome

The production registry contains twelve sorted definitions and twelve exact public registrations. Every service in the reusable dependency graph shares the same immutable registry, atomic journal reader, secure-reference store, and supervisor. Censal REVIEW has one domain-owned bearer-free field projector and exact response schema; result schemas remain deliberately absent where terminal references are opaque and no registered public refresh adapter consumes them.

The frontend-neutral facade now exposes public operation contracts and services while keeping persistence, replay, interaction checkpoint, and bearer mechanics private. Real pre-login and active-profile integration proves graph construction before custody acquisition, the registry contract-set digest, shared adapters, authority-bound response construction, and process shutdown path.

## Notes

No compatibility shim, re-export alias, fake adapter, patch, skip, or xfail was introduced. CLI, MCP, and TUI call-site cutover remains owned by later plan steps; this step supplies their sole composition seam without changing frontend invocation paths.

## Verification

- `pytest -q -m "unit or integration"` over the application-operation, operation-persistence, auth-definition, user-profile-definition/censal, filed-history, and composition matrix passed 440 S122 tests. Five separately staged S123 receipt-validator cases errored only because their subprocess could not find a running Vaultspec RAG service; S123 remains open and those cases are not counted as S122 evidence.
- Focused current composition and filed-history integration verification passed after the safe `OperationLogSeverity` facade cutover; the owner lane separately records its 17 filed-history integration passes.
- Targeted facade/composition Ruff lint and formatting and `ty check` passed. Focused BasedPyright retains LOW owner-private diagnostics in `_composition.py`; the independent review found no HIGH or CRITICAL boundary issue.
- Vaultspec RAG followed by exact construction census found one production `OperationRegistry(...)` in `entrypoints/_operation_composition.py` and one production `OperationSupervisor(...)` in `application/operations/_composition.py`. The only other hits are the canonical class declarations and tests.
- Post-relocation RAG lands first on `application/operations/owner.py`; exact declaration and import searches prove that it is the sole executor-contract definition home, `_executor.py` is absent, and no shim or re-export bridge remains.
- Exact import census returned no private operation imports from entrypoints or inbound frontends. Safe cross-package imports are constrained to `OperationLogSeverity`, `OperationResponseIntent`, and `OperationEventCursor`; raw events, interaction checkpoints/tokens, journal/snapshot/lease records, replay pages, and response bearers remain outside the public facade.
- Independent review is recorded in `2026-08-24-tui-architecture-s122-operation-composition-review-audit`; any HIGH or CRITICAL finding must be remediated before this step is closed.
