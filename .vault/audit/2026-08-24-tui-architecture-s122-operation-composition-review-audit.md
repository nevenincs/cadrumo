---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:040d7b7c5c21e1721196895c07e3d997fb00dafdd85df9839ab1b376b6a19655'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `s122 operation composition review`

## Scope

Reviewed `W02.P19.S122` against the accepted operation-envelope decision and the live production composition. The review covered `src/cadrumo/entrypoints/_operation_composition.py`, the operation public facade and projection services, auth, user-profile, censal and filed-history definition builders and owner facades, operation journal, lease and secure-reference adapters, lazy active-profile persistence, exact public contract registration, production-definition completeness, duplicate composition authorities, private-import boundaries, and focused real-adapter tests.

## Findings

### review-response-authority | high | The public REVIEW path persists its bearer yet exposes no public apply or reject service

`CensalOperationRequest` includes `response_token`, the production registration publishes that exact request schema, and the definition stores the request through `SECURE_REFERENCE`; the executor later reconstructs the pending interaction from `request.payload.response_token` at `src/cadrumo/application/user_profile/_censal_operation.py:174`, `src/cadrumo/application/user_profile/_censal_operation.py:181`, `src/cadrumo/application/user_profile/_censal_operation.py:392`, and `src/cadrumo/application/user_profile/_censal_operation.py:492`. This contradicts the runtime-only, non-persisted bearer boundary. At the same time, the composed `response` dependency returns only `OperationResponseControlService`, whose sole operation is read-only `inspect`; the facade exports no public apply or reject request/service, and the only concrete token-binding authority is private at `src/cadrumo/application/operations/_projection_services.py:102`. A CLI, MCP, or later TUI consumer therefore cannot complete REVIEW through the public seam without reaching private response types or the raw supervisor, while a restart-capable secure request retains the bearer material that observation must not recreate.

Resolution (2026-08-24): resolved during review. The censal request and its durable secure-reference payload no longer contain a response token. The supervisor now mints the REVIEW token only after publishing the exact pending checkpoint and associates it with a pre-reserved process-local capability. Submission returns an opaque, actor-bound, non-serializable capability separately from its safe receipt; response binding requires that capability and exact operation, interaction, revision, pending checkpoint, and actor. Forged, mismatched, stale, and restarted-process claims fail without consuming the valid reservation. A successful bind consumes the capability once and the public response service exposes strict V1 `apply` and `reject` mutations while keeping the token and raw response intent private.

### mcp-projection-contract | medium | Every production definition excludes MCP from its declared frontend contract

`OperationFrontendProjection` contains only `CLI` and `TUI` at `src/cadrumo/application/operations/_registry.py:244`, and every composed auth, profile, censal and filed-history definition registers only that pair. The resulting exact public contracts cannot declare MCP as a permitted projection even though the accepted architecture and S122 require the same frontend-neutral composition to serve MCP. This is contract drift rather than a missing call-site alone: adding an MCP consumer later would either contradict every current definition digest or require a breaking contract-set replacement.

Resolution (2026-08-24): resolved during review. `OperationFrontendProjection` now includes MCP and all twelve production definition contracts declare exactly CLI, MCP, and TUI. The rebuilt immutable contract set reproduces those closed values for every registration.

### auth-provider-schema | medium | Public auth operation requests leave the closed provider axis as an unrestricted string

`AuthConfigureOperationRequest.provider`, `AuthSessionAcquireOperationRequest.provider`, and `AuthTeardownOperationRequest.provider` are `str` or `str | None` at `src/cadrumo/application/auth/_operation_definitions.py:62`, `src/cadrumo/application/auth/_operation_definitions.py:69`, and `src/cadrumo/application/auth/_operation_definitions.py:77`. These models are now exact public schema identities, but the repository already owns the closed `AuthProviderKind` enum. The published contracts therefore accept arbitrary provider tokens and defer rejection past the typed boundary, contrary to the closed-axis rule and the exact-schema claim.

Resolution (2026-08-24): resolved during review. The three exact public request models now use `AuthProviderKind` or its optional form and convert to legacy string-shaped callees only inside the owner executor boundary.

### facade-cut-boundary | medium | The narrowed facade forces production composition and owner packages onto private operation modules

The current facade cut removes the earlier raw exports, but the production seam now imports `OperationSecureResponseAuthority` and `OperationSupervisor` directly from private operation modules at `src/cadrumo/entrypoints/_operation_composition.py:29` and `src/cadrumo/entrypoints/_operation_composition.py:30`. Auth and user-profile definitions likewise import `OperationExecutorContext` privately, and the censal owner imports `OperationConsumedInteraction`, `OperationInteractionRequest`, `OperationPendingInteraction`, and raw `OperationResponseIntent` from `operations._interactions` at `src/cadrumo/application/user_profile/_censal_operation.py:46`. The sole composition seam and cross-package application owners therefore cannot build against the sole canonical public facade, violating the no-private-cross-package boundary and making future consumers choose between an insufficient facade and private implementation contracts.

Resolution (2026-08-24): resolved during review. Runtime-private supervisor and bearer assembly moved behind `compose_operation_services`; the entrypoint consumes only the canonical public facade and exposes `OperationComposedServices`. Auth, user-profile, censal, and live owners consume their narrow executor contributor contracts through that facade. The temporary owner re-export bridge was deleted, the exact production private-import census is empty, and facade tests exclude raw events, snapshots, journals, leases, replay pages, interaction checkpoints, response tokens, response intent, supervisor, and concrete response authority.

## Recommendations

- Add one public, bearer-authorized response mutation service with strict V1 apply and reject inputs, keep concrete bearer construction and token material runtime-only, and remove the token from the censal public/persisted request. Prove restart observation cannot recreate response authority and public consumers need no private response types.
- Decide and encode MCP in the closed frontend-projection contract before publishing the current contract-set digest for S122, or explicitly narrow the authorizing decision and Step if MCP is not a distinct projection.
- Type all three public auth provider fields as `AuthProviderKind` and convert to plain strings only at the existing legacy-shaped callee boundary.
- Expose narrow public contributor and composition protocols sufficient for the production root and domain-owned executors, or relocate the composition authority so no cross-package caller imports `application.operations._*`; keep bearer construction and raw response intent private.

All recommendations were implemented and independently rechecked in the final review snapshot. No open finding remains. Verdict: approve S122 for closure by the owning executor.
## Re-review at `dad420acca1` (2026-08-25)

### Final disposition â€” PASS

The prior HIGH facade-authority finding is resolved at exact commit `dad420acca18f1cc3cd2eb68e5c8d0b87681999d`. Vaultspec RAG semantic discovery was followed by exact commit-scoped searches and source reads.

- `cadrumo.application.operations` no longer exports supervisor, executor/context, interaction-access, response-capability/authority, secure-operand, secret-submission, or persistence primitives. Its negative export test explicitly rejects those symbols.
- `cadrumo.application.operations.owner` is a narrow owner-only re-export of the canonical `_executor` objects: identity assertions prove no redeclaration. Production auth, live, and user-profile owners import those contributor contracts from `operations.owner`; exact search finds no non-test entrypoint import of it.
- The entrypoint imports only `OperationComposedServices`, `OperationRegistry`, and `compose_operation_services` from the inbound-safe facade. `OperationComposedServices` exposes only submission, observation, REVIEW, refresh, cancellation, and detach as public fields; registry and supervisor remain internal.
- The former static definition-ID list is replaced by a live owner-facade fixed point: current auth, user-profile, censal, and filed-history definition and registration builders are recomposed as the independently derived denominator and compared with production registry and contract-set composition.
- The opaque response capability remains separately held: it is issuer-gated, actor- and operation-bound, non-serializable, consumed on successful bind, zeroized on close, and unavailable after process restart. Public apply/reject V1 requests bind through the composed service without exposing the token or concrete authority.

Focused faÃ§ade, composition, fixed-point, opaque-capability, and entrypoint-owner-boundary tests passed in the repository test runner; Ruff passed on all changed surfaces. Exact source searches also found no non-test duplicate production `OperationRegistry(` or `OperationSupervisor(` construction outside the composition path.

### LOW â€” Focused basedpyright remains red inside owner-private composition

`basedpyright` reports five diagnostics in `application/operations/_composition.py`: three private cross-module references (`_read_snapshot`, `_UnavailableOperationSecureResponseAuthority`, `_UnavailableSnapshot`) and two unknown-type diagnostics around `TypeAdapter(OperationActorReference).validate_python`. These are owner-private implementation/type-quality issues, not a public authority exposure or redeclaration, and do not alter the D0/D8 disposition. They should be cleaned up before a broader quality-gate milestone.

No HIGH or CRITICAL finding remains. S122 may close.
