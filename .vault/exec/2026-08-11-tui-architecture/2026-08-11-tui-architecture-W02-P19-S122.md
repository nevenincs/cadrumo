---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:55c83b56a0093d94dd9f0a641a336025db01f7fe34b7be6fa2e6ef07919d7986'
step_id: 'S122'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Export the sole public operation contract family and compose the immutable production registry, observation, REVIEW, refresh, response, cancel, and detach services with real adapters through one import-light entrypoint seam consumed by CLI, MCP, and the later TUI launcher

## Scope

- `src/cadrumo/application/operations/__init__.py and src/cadrumo/entrypoints/_operation_composition.py`

## Description

- Promoted public definition-registration builders through the auth, user-profile, and live application facades.
- Registered every shipped auth, profile-maintenance, censal REVIEW, and filed-history definition in one deterministic production registry.
- Added the import-light `OperationProductionDependencies` composition with real journal, lease, secure-reference, provenance, supervisor, observation, REVIEW, refresh, cancellation, detach, response-authority, and shutdown wiring.
- Narrowed `cadrumo.application.operations` so frontend consumers cannot import raw events, interactions, snapshots, journals, leases, replay records, response tokens, or bound bearers.
- Replaced the secret-capable nested bundle-export operation request with a credential-free public request and kept the passphrase solely in one-shot custody.
- Removed the duplicate default-registration construction shape through `compose_request_only`.
- Retargeted persistence and application implementation imports to their canonical owning modules after the facade cut.
- Used semantic discovery before implementation and again after the cut to verify the production composition and registration producer fixed points.

## Outcome

The production registry contains twelve sorted definitions and twelve exact public registrations. Every service in the reusable dependency graph shares the same immutable registry, atomic journal reader, secure-reference store, and supervisor. Censal REVIEW has one domain-owned bearer-free field projector and exact response schema; result schemas remain deliberately absent where terminal references are opaque and no registered public refresh adapter consumes them.

The frontend-neutral facade now exposes public operation contracts and services while keeping persistence, replay, interaction checkpoint, and bearer mechanics private. Real active-profile integration proves the registry contract-set digest, shared adapters, authority-bound response construction, and process shutdown path.

## Notes

No compatibility shim, re-export alias, fake adapter, patch, skip, or xfail was introduced. CLI, MCP, and TUI call-site cutover remains owned by later plan steps; this step supplies their sole composition seam without changing frontend invocation paths.
