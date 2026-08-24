---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8d4a40191bd0c6360239248611758395deee9f02b9e2458f0d6507597515c054'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s122 operation composition review`

## Scope

Reviewed `W02.P19.S122` against the accepted operation-envelope decision and the live production composition. The review covered `src/cadrumo/entrypoints/_operation_composition.py`, the operation public facade and projection services, auth, user-profile, censal and filed-history definition builders and owner facades, operation journal, lease and secure-reference adapters, lazy active-profile persistence, exact public contract registration, production-definition completeness, duplicate composition authorities, private-import boundaries, and focused real-adapter tests.

## Findings

### review-response-authority | high | The public REVIEW path persists its bearer yet exposes no public apply or reject service

`CensalOperationRequest` includes `response_token`, the production registration publishes that exact request schema, and the definition stores the request through `SECURE_REFERENCE`; the executor later reconstructs the pending interaction from `request.payload.response_token` at `src/cadrumo/application/user_profile/_censal_operation.py:174`, `src/cadrumo/application/user_profile/_censal_operation.py:181`, `src/cadrumo/application/user_profile/_censal_operation.py:392`, and `src/cadrumo/application/user_profile/_censal_operation.py:492`. This contradicts the runtime-only, non-persisted bearer boundary. At the same time, the composed `response` dependency returns only `OperationResponseControlService`, whose sole operation is read-only `inspect`; the facade exports no public apply or reject request/service, and the only concrete token-binding authority is private at `src/cadrumo/application/operations/_projection_services.py:102`. A CLI, MCP, or later TUI consumer therefore cannot complete REVIEW through the public seam without reaching private response types or the raw supervisor, while a restart-capable secure request retains the bearer material that observation must not recreate.

### mcp-projection-contract | medium | Every production definition excludes MCP from its declared frontend contract

`OperationFrontendProjection` contains only `CLI` and `TUI` at `src/cadrumo/application/operations/_registry.py:244`, and every composed auth, profile, censal and filed-history definition registers only that pair. The resulting exact public contracts cannot declare MCP as a permitted projection even though the accepted architecture and S122 require the same frontend-neutral composition to serve MCP. This is contract drift rather than a missing call-site alone: adding an MCP consumer later would either contradict every current definition digest or require a breaking contract-set replacement.

### auth-provider-schema | medium | Public auth operation requests leave the closed provider axis as an unrestricted string

`AuthConfigureOperationRequest.provider`, `AuthSessionAcquireOperationRequest.provider`, and `AuthTeardownOperationRequest.provider` are `str` or `str | None` at `src/cadrumo/application/auth/_operation_definitions.py:62`, `src/cadrumo/application/auth/_operation_definitions.py:69`, and `src/cadrumo/application/auth/_operation_definitions.py:77`. These models are now exact public schema identities, but the repository already owns the closed `AuthProviderKind` enum. The published contracts therefore accept arbitrary provider tokens and defer rejection past the typed boundary, contrary to the closed-axis rule and the exact-schema claim.

### facade-cut-boundary | medium | The narrowed facade forces production composition and owner packages onto private operation modules

The current facade cut removes the earlier raw exports, but the production seam now imports `OperationSecureResponseAuthority` and `OperationSupervisor` directly from private operation modules at `src/cadrumo/entrypoints/_operation_composition.py:29` and `src/cadrumo/entrypoints/_operation_composition.py:30`. Auth and user-profile definitions likewise import `OperationExecutorContext` privately, and the censal owner imports `OperationConsumedInteraction`, `OperationInteractionRequest`, `OperationPendingInteraction`, and raw `OperationResponseIntent` from `operations._interactions` at `src/cadrumo/application/user_profile/_censal_operation.py:46`. The sole composition seam and cross-package application owners therefore cannot build against the sole canonical public facade, violating the no-private-cross-package boundary and making future consumers choose between an insufficient facade and private implementation contracts.

## Recommendations

- Add one public, bearer-authorized response mutation service with strict V1 apply and reject inputs, keep concrete bearer construction and token material runtime-only, and remove the token from the censal public/persisted request. Prove restart observation cannot recreate response authority and public consumers need no private response types.
- Decide and encode MCP in the closed frontend-projection contract before publishing the current contract-set digest for S122, or explicitly narrow the authorizing decision and Step if MCP is not a distinct projection.
- Type all three public auth provider fields as `AuthProviderKind` and convert to plain strings only at the existing legacy-shaped callee boundary.
- Expose narrow public contributor and composition protocols sufficient for the production root and domain-owned executors, or relocate the composition authority so no cross-package caller imports `application.operations._*`; keep bearer construction and raw response intent private.
