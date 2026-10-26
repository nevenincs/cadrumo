---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:eb51671d40def64041beaba681eba24d849d2a2b2c8d65be8c2822d84f331f9c'
related: []
---

# `tui-architecture` audit: `s122 operation composition review`

## Scope

Reviewed `W02.P19.S122` against the accepted operation-envelope decision and the live production composition.

## Findings

### review-response-authority | high | The public REVIEW path persists its bearer yet exposes no public apply or reject service

This contradicts the runtime-only, non-persisted bearer boundary. A CLI, MCP, or later TUI consumer therefore cannot complete REVIEW through the public seam without reaching private response types or the raw supervisor, while a restart-capable secure request retains the bearer material that observation must not recreate.

Resolution (2026-08-24): resolved during review. The censal request and its durable secure-reference payload no longer contain a response token. The supervisor now mints the REVIEW token only after publishing the exact pending checkpoint and associates it with a pre-reserved process-local capability. Submission returns an opaque, actor-bound, non-serializable capability separately from its safe receipt; response binding requires that capability and exact operation, interaction, revision, pending checkpoint, and actor. Forged, mismatched, stale, and restarted-process claims fail without consuming the valid reservation. A successful bind consumes the capability once and the public response service exposes strict V1 `apply` and `reject` mutations while keeping the token and raw response intent private.

### mcp-projection-contract | medium | Every production definition excludes MCP from its declared frontend contract

The resulting exact public contracts cannot declare MCP as a permitted projection even though the accepted architecture and S122 require the same frontend-neutral composition to serve MCP. This is contract drift rather than a missing call-site alone: adding an MCP consumer later would either contradict every current definition digest or require a breaking contract-set replacement.

Resolution (2026-08-24): resolved during review. `OperationFrontendProjection` now includes MCP and all twelve production definition contracts declare exactly CLI, MCP, and TUI. The rebuilt immutable contract set reproduces those closed values for every registration.

### auth-provider-schema | medium | Public auth operation requests leave the closed provider axis as an unrestricted string

These models are now exact public schema identities, but the repository already owns the closed `AuthProviderKind` enum. The published contracts therefore accept arbitrary provider tokens and defer rejection past the typed boundary, contrary to the closed-axis rule and the exact-schema claim.

Resolution (2026-08-24): resolved during review. The three exact public request models now use `AuthProviderKind` or its optional form and convert to legacy string-shaped callees only inside the owner executor boundary.

### facade-cut-boundary | medium | The narrowed facade forces production composition and owner packages onto private operation modules

The sole composition seam and cross-package application owners therefore cannot build against the sole canonical public facade, violating the no-private-cross-package boundary and making future consumers choose between an insufficient facade and private implementation contracts.

Resolution (2026-08-24): resolved during review. Runtime-private supervisor and bearer assembly moved behind `compose_operation_services`; the entrypoint consumes only the canonical public facade and exposes `OperationComposedServices`. Auth, user-profile, censal, and live owners consume their narrow executor contributor contracts through that facade. The temporary owner re-export bridge was deleted, the exact production private-import census is empty, and facade tests exclude raw events, snapshots, journals, leases, replay pages, interaction checkpoints, response tokens, response intent, supervisor, and concrete response authority.

## Recommendations

- Add one public, bearer-authorized response mutation service with strict V1 apply and reject inputs, keep concrete bearer construction and token material runtime-only, and remove the token from the censal public/persisted request. Prove restart observation cannot recreate response authority and public consumers need no private response types.
- Decide and encode MCP in the closed frontend-projection contract before publishing the current contract-set digest for S122, or explicitly narrow the authorizing decision and Step if MCP is not a distinct projection.
- Type all three public auth provider fields as `AuthProviderKind` and convert to plain strings only at the existing legacy-shaped callee boundary.
- Expose narrow public contributor and composition protocols sufficient for the production root and domain-owned executors, or relocate the composition authority so no cross-package caller imports `application.operations._*`; keep bearer construction and raw response intent private.

All recommendations were implemented and independently rechecked in the final review snapshot. No open finding remains. Verdict: approve S122 for closure by the owning executor.
## Re-review at `dad420acca1` (2026-08-25)

### Final disposition ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ PASS

The prior HIGH facade-authority finding is resolved at exact commit `dad420acca18f1cc3cd2eb68e5c8d0b87681999d`. Vaultspec RAG semantic discovery was followed by exact commit-scoped searches and source reads.

- `cadrumo.application.operations` no longer exports supervisor, executor/context, interaction-access, response-capability/authority, secure-operand, secret-submission, or persistence primitives. Its negative export test explicitly rejects those symbols.
- `cadrumo.application.operations.owner` is a narrow owner-only re-export of the canonical `_executor` objects: identity assertions prove no redeclaration. Production auth, live, and user-profile owners import those contributor contracts from `operations.owner`; exact search finds no non-test entrypoint import of it.
- The entrypoint imports only `OperationComposedServices`, `OperationRegistry`, and `compose_operation_services` from the inbound-safe facade. `OperationComposedServices` exposes only submission, observation, REVIEW, refresh, cancellation, and detach as public fields; registry and supervisor remain internal.
- The former static definition-ID list is replaced by a live owner-facade fixed point: current auth, user-profile, censal, and filed-history definition and registration builders are recomposed as the independently derived denominator and compared with production registry and contract-set composition.
- The opaque response capability remains separately held: it is issuer-gated, actor- and operation-bound, non-serializable, consumed on successful bind, zeroized on close, and unavailable after process restart. Public apply/reject V1 requests bind through the composed service without exposing the token or concrete authority.

Focused faÃƒÆ’Ã‚Â§ade, composition, fixed-point, opaque-capability, and entrypoint-owner-boundary tests passed in the repository test runner; Ruff passed on all changed surfaces. Exact source searches also found no non-test duplicate production `OperationRegistry(` or `OperationSupervisor(` construction outside the composition path.

### LOW ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬ Focused basedpyright remains red inside owner-private composition

`basedpyright` reports five diagnostics in `application/operations/_composition.py`: three private cross-module references (`_read_snapshot`, `_UnavailableOperationSecureResponseAuthority`, `_UnavailableSnapshot`) and two unknown-type diagnostics around `TypeAdapter(OperationActorReference).validate_python`. These are owner-private implementation/type-quality issues, not a public authority exposure or redeclaration, and do not alter the D0/D8 disposition. They should be cleaned up before a broader quality-gate milestone.

No HIGH or CRITICAL finding remains. S122 may close.
## Canonical relocation re-review at `033a058f57` (2026-08-25)

### Superseding disposition - PASS

This section supersedes the temporary `dad420acca1` statement that `operations.owner` re-exported canonical `_executor` objects. Under the clarified rule, that intermediate identity-re-export shape was noncompliant: it was a compatibility bridge and cannot be retained.

Commit `033a058f57e0c110a990d5d373ce5d5a221d7baf` resolves it by deleting `application/operations/_executor.py` and defining the owner-only executor protocols directly in `application/operations/owner.py`. The facade census now proves their `__module__` is `operations.owner`, and exact source search finds no production import of `operations._executor`, no `_executor.py`, and no compatibility re-export.

Production auth, live, user-profile, and export owners import contributor contracts directly from `operations.owner`. No non-test entrypoint imports that module. The top-level `application.operations` facade continues to reject every owner/runtime/custody symbol while the entrypoint imports only `OperationComposedServices`, `OperationRegistry`, and `compose_operation_services` from the inbound-safe facade.

S123 remains valid: its exact authority/constructor census does not retain `_executor` as an expected authority, and its resident Vaultspec RAG query/replay remains source-tree-bound and limited to canonical operation authorities. Focused Ruff and basedpyright for the relocated owner, facade, supervisor, and S123 validator are clean.

No finding remains. S122 and S123 pass this relocation re-review.
