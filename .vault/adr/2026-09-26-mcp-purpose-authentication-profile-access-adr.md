---
tags:
  - '#adr'
  - '#mcp-purpose-authentication'
date: '2026-09-26'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:7ae038b89f704669b6d13d909163aadbdc038bc0896c406ac6d5f2d2f8c3384d'
related:
  - "[[2026-09-26-mcp-purpose-authentication-reference]]"
  - "[[2026-09-26-mcp-purpose-authentication-research]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-08-13-profile-session-lifecycle-successor-adr]]"
  - "[[2026-08-13-cli-action-envelope-successor-adr]]"
  - "[[2026-09-04-tui-architecture-authenticated-tui-visibility-adr]]"
  - '[[2026-09-26-mcp-purpose-authentication-adr]]'
---

# `mcp-purpose-authentication` adr: profile API keys, delegated sessions and CLI/TUI parity | (**status:** `accepted`)

## Problem Statement

Enable a local agent to authenticate an exact Cadrumo profile and resume authorized work without repeating the human password journey on every connection. CLI and TUI must each operate the complete API-key, authentication and session-lock lifecycle.

This record owns delegated authority, protected automation unlock, credential/session transitions and interface parity. Local runtime placement and execution boundaries belong to 2026-09-26-mcp-purpose-authentication-adr. Runtime management, including health monitoring, service installation, start/stop/status controls and restart supervision, is explicitly excluded from both records and deferred to application bundling, building and provisioning. Evidence belongs to the related Reference and Research.

## Considerations

The operator confirmed local deployment, concurrent agents with separately tracked sessions, autonomous API authentication and full CLI/TUI parity. The initial 2026-09-26 authorization stopped at document persistence. After the documented handoff, the operator instructed continuation; that authorizes the presented design and plan within their stated local scope.

The custody and admission gaps are recorded in 2026-09-26-mcp-purpose-authentication-reference. The distinction between local API credentials, MCP transport authorization and remote-provider authentication is evaluated in 2026-09-26-mcp-purpose-authentication-research.

## Considered options

- Extend human login indefinitely: rejected because delegation and human timeout would become the same authority.
- Share the profile password or data key with agents: rejected because operational scope and independent revocation would be unenforceable at the application boundary.
- Store only a token verifier and reuse a locked profile: rejected because credential verification alone supplies no means to decrypt profile data.
- Bind a revocable API key to a durable grant and a separate protected unlock capability: selected. It permits autonomous reconnect while preserving bounded sessions and explicit user control.
- Require hosted OAuth for a local installation: rejected. Remote transport and provider authentication remain separate concerns.

## Constraints

This is an explicit extension of 2026-08-13-profile-password-custody-rollup-adr, not an alternate interpretation of its human acceleration receipt. Its password and recovery doors remain independently usable. The application lifecycle owner in 2026-08-13-profile-session-lifecycle-successor-adr remains authoritative; frontends cannot publish synthetic authenticated state.

The focused custody/session amendments identify this delegated door and context-specific binding; their unrelated rules remain authoritative.

The established CLI action envelope remains the machine contract under 2026-08-13-cli-action-envelope-successor-adr. Human TUI visibility remains governed by 2026-09-04-tui-architecture-authenticated-tui-visibility-adr. A restricted API-key login is not proof of full human-owner authority.

## Implementation

### Principals and authority

One OS user plus canonical storage root owns a local runtime boundary. Ephemeral OS login-session provenance is distinct from application-session identity and is not part of durable grant binding. A profile has an immutable internal identity independent of its display label. Multiple password-protected profiles may share an OS account; this does not provide isolation against hostile code running as that same OS user.

An automation grant binds an immutable profile, installation and OS owner, enrolled client identity, allowed operation scopes, allowed data projections and disclosure destination, optional tax-period constraints, unattended/OS-lock policy, explicit validity interval, and revocation/custody generations. No ambient active-profile or all-profiles default applies.

An API key is a high-entropy opaque authentication secret for that grant. It is neither a DEK, profile password, OAuth access token nor an AEAT credential. The server retains a verifier and protected grant state; the enrolled local client retains the secret in an approved secret store. A non-secret key identifier supports inventory and revocation.

Each admitted connection receives an independent short-lived session bound to that grant and exact profile. A host may share one enrolled key across its workers, but each connection has its own session identity. Self-reported agent names are attribution, not authenticated identities. Distinct clients needing independently attributable root credentials enroll separate keys.

A coordinator may obtain narrower child sessions where its grant allows delegation. Child permissions and expiry cannot exceed the parent, and revocation cascades. A multiplexed host that cannot separate callers is one security principal. Ordinary API keys never create root grants, broaden scope, renew grant validity or change custody.

Effective permission is the intersection of grant, child/session restrictions, current operation policy, output consent, backend readiness and applicable published-authority grade. Possession of an operation ID or observation cursor adds no authority. Response/apply capabilities remain separate and transaction-bound.

### Authentication capability matrix

| Activity | Required authority | What it establishes |
| --- | --- | --- |
| Public capability discovery and tax-authority queries | Local connection; applicable valid publication for tax facts | Public access only |
| Human CLI/TUI profile login | Explicit profile and password; bounded valid human receipt may resume | Human session with its own timeout |
| Attended agent access | Explicit delegation tied to a valid human authorization | Access ending no later than that authorization |
| Unattended agent, machine CLI or restricted TUI login | Active enrolled API key/grant plus available protected unlock capability | Fresh bounded session for the exact profile |
| Key enrollment, rotation, grant renewal or expansion | Fresh profile-password proof and exact local consent | Only the reviewed change; never implicit elevation |
| Inspect/manage profile grants and sessions | Human profile authority; fresh password where expanding access or unlocking globally | Profile administration |
| Lock/revoke the caller's own session | That session's authority | Terminates only that session and its descendants |
| Read/acquire from AEAT | Local permission and independently verified provider/taxpayer authorization | Only the requested remote capability |
| Live filing/signing | Separate validated workflow and transaction-specific authorization | Not enabled by this feature |

### Enrollment and first login

1. A new adapter or machine client can connect without an unlocked profile and inspect non-private status. Requesting private work without a matching key returns an authorization-required result.
2. Cadrumo creates a bounded single-use request binding the requesting connection, enrolled-client candidate, exact profile, requested scopes, output destination and duration. A pending request ID is safe to show; it is not authorization.
3. The user opens either trusted CLI or TUI, inspects that request and proves the profile password through the dedicated secret channel. A password login elsewhere does not approve a waiting request.
4. The user approves attended access or explicitly enables unattended access, including whether it may continue during OS lock. Approval binds the exact request and reviewed permissions. Decline, expiry, mismatch and cancellation leave no active grant.
5. For unattended enrollment, Cadrumo stages the grant, verifier and separately protected profile unlock material. The API key is delivered directly into the enrolled client's approved secret store, or through an explicit one-time protected channel. Normal results contain only a credential reference.
6. Activation occurs only when enrollment and protected delivery are consistent. Request identity provides idempotency. Delivery failure rolls back or leaves a non-usable recoverable enrollment; it must not expose an active orphan credential.
7. The client proves possession to the authenticated local runtime. Grant identity, target profile, OS/installation binding, scope, expiry, revocation and custody generations are checked before data access. The runtime then issues a fresh session.

Passwords, keys, recovery values and unlock material never enter MCP arguments/results, elicitation forms, chat, ordinary JSON/text output, argv, environment values, clipboard defaults, logs or plaintext temporary files. MCP configuration contains an opaque credential reference. CLI secret input composes the existing bounded stdin/descriptor protocol; key delivery is a separate protected output capability, never the general stdout envelope. TUI uses masked secret entry and protected-store selection. Exact channel ownership and inherited-handle behavior must be proven on each OS.

### Protected automation custody

The API key is checked independently from an automation-specific encrypted wrap of the already-proven profile DEK. The wrap's authenticated binding includes grant, profile, installation, custody generation and DEK epoch. Its protection resides in the approved OS secret boundary. A copied profile database or API key alone is insufficient.

Grant admission and sealed unlock records must be usable before the profile opens. This is an explicit optional custody subsystem outside the locked profile, with protected sensitive metadata and atomic lifecycle transitions; it is not another taxpayer-data store. The client key store, server verifier and unwrap protection have distinct purposes even where one OS credential facility backs them.

Enabling unattended access deliberately adds another way this installation can obtain the DEK after human logout. Show that fact before enrollment and whenever the user inspects remaining access. Never expose the DEK to an agent or let an API key open the database outside the application.

Revocation removes the usable grant unlock protection and invalidates sessions. Stale control records and generation mismatches fail closed. Portable profile backups exclude automation keys, grants and unlock material; restore or movement to another installation requires fresh enrollment. Restoring an old profile must not resurrect revoked automation. Full compromise of the OS credential boundary is outside this protection claim.

Unavailable or unsuitable OS secret facilities refuse unattended enrollment/resume, with no plaintext fallback. Password login must remain possible without the optional automation subsystem. The settled security contract below defines persisted binding, cryptographic composition and OS backend admission; implementation must prove those properties using the existing primitives.

### Settled security contract

The operator's instruction to continue after presentation of the two ADRs and plan authorizes settlement of this local, profile-scoped design. Product execution scope is recorded separately in the plan. The following choices resolve the first plan prerequisite; they do not claim platform validation.

API keys use a versioned product discriminator, a random UUID key identifier and 32 independently random secret bytes encoded as unpadded base64url. The identifier is not a secret. Generation uses the OS-backed cryptographic random source. The verifier is SHA-256 over a domain-separated canonical encoding of version, key identifier and secret; comparison is constant-time. A deliberately high-entropy machine secret uses this verifier rather than the password KDF. Neither verifier nor identifier grants access without proving the secret, active grant and protected custody.

Use the existing AES-256-GCM persistence primitive for the new automation record, with fresh 12-byte nonces and full tags. Do not extend the human acceleration-receipt schema or reuse its key. A versioned canonical outer record names only routing identities, generation and ciphertext. Its authenticated data binds product/purpose, schema, installation, immutable profile, grant, control revision, custody generation and DEK epoch. Sensitive grant metadata, verifier and wrapped-DEK material stay sealed; no unencrypted tax values enter the control store.

Each profile has its own random control-store key, protected in the OS credential store independently of other profiles and of the profile password. Each grant has a separate random DEK wrapping key in that store. The control anchor carries the current control revision and encrypted-record digest alongside its key. Validate the anchor, record, grant and current profile custody before unwrapping; then authenticate the existing profile DEK sentinel. A filesystem record with an older revision/digest cannot reactivate a revoked key. A coherent rollback of OS secrets and all witnesses remains outside the guarantee, as does OS-account compromise.

Control updates have one serialized application owner and a recoverable publication protocol: write and fsync the sealed successor and bounded transaction intent, publish/read-back-verify the matching OS anchor, then publish the current pointer. Recovery follows only the anchor-matching successor or the still-authoritative predecessor; unexplained mixtures refuse automation. The journal contains only safe transaction identities and record digests. It never contains the API secret, wrapping key, DEK or private grant payload. File and keychain writes are not claimed to be one atomic transaction.

Enrollment creates an inactive candidate, delivers the key through the approved private channel, and requires possession plus a verified client-store handoff before activating its grant. A crash before activation leaves no authorized credential; retry reconciles or replaces the candidate without re-displaying its secret. Rotation follows the same protocol and retires the predecessor after at most 60 seconds of overlap. Failed handoff leaves the predecessor within its unchanged validity, rather than falsely reporting a replacement.

Select native Windows Credential Manager, macOS Keychain, or Linux Secret Service explicitly. A positive keyring priority, arbitrary plugin or plaintext/file backend is insufficient. Use separate product namespaces for client credentials, profile control anchors and per-grant wrap keys. Background access must never launch a credential prompt; a locked store yields a typed unavailable/needs-user state. KWallet and additional stores are unavailable until their non-prompting, atomic replacement and deletion semantics pass the same adapter contract.

Fresh password proof for enrollment, rotation, extension, scope expansion and global unlock is bound to one exact administration request and expires after five minutes; it is not reusable merely because the human session is live. Default grant validity is 365 days with an explicit user-selected end date. The access lease maximum is five minutes, always clipped to parent and grant expiry. Rotation does not change either ceiling. Expiry checks use UTC deadlines with a monotonic within-process budget; detected clock rollback invalidates affected leases and requires fresh admission.

Revocation first fences new admission, data release and local commit under the profile authority, durably records denial, advances the protected control state, and retires affected unwrap keys. The acknowledgement distinguishes access denied from pending physical credential-store cleanup. If the store is unavailable, surviving cleanup intent keeps automation disabled across restart; it cannot be discarded to restore access. Password-authorized normal work remains independent of automation-store health. Password or recovery transitions invalidate old grants through custody generation and the denial fence even when key deletion must be retried.

A single-session lock ends that session, while a valid root key may establish another. Profile-wide lock suspends all grants until fresh password-authorized selection of which to reactivate. Reconnection always creates a new session bound to the runtime boot identity and local connection; a session ID is never a portable bearer. Child-connection tickets, when supported, are one-shot, short-lived protected handoffs restricted to the parent's grant and scopes, not new root API keys.

This contract reuses the cryptographic and custody patterns located in the Reference. Native store behavior, secure delivery and crash injection remain implementation acceptance obligations.

### Fresh sessions, target binding and status

Every restart resolves the protected credential reference and authenticates anew. MCP initialization, a remembered identity read and a cached logged-in flag cannot establish access.

Status reports separate facts: connection, credential authentication, grant validity, profile binding, session expiry, storage availability, authority availability and effective capabilities. Provider state is reported separately. Refusals provide non-secret next actions such as authenticate, renew, unlock, reconnect or resolve unavailable custody.

Each private call and result/resource read validates the live session, current generations, immutable target and scope. A conflicting profile argument refuses; it cannot retarget the session. Human CLI/TUI hot-profile selection belongs to its own context. Switching from A to B does not switch an agent or durable operation for A.

### Four lifetimes

Human sessions keep their own idle/absolute settings; polling and API activity never prolong human login. Human and attended sessions depend on their originating OS login context; logout invalidates them and their descendants even when another login exists. Attended access is bounded by its parent human authorization. Independent API grants survive that logout. Unattended continuation or re-admission requires a specifically verified eligible login context, available required credential facilities and permitting grant policy. Another login's existence alone proves none of those dependencies; unknown eligibility refuses dependent work. OS observations come only from trusted lifecycle owners. Runtime loss invalidates live leases and a replacement requires fresh admission.

The automation grant has an explicit user-approved calendar end date. The enrollment default is 365 days, adjustable by the user; it is not a perpetual credential. Grant extension or scope expansion requires fresh password authorization.

API keys may expire earlier and rotate within that grant interval. Rotation requires fresh human proof, delivers the replacement securely, and allows only a bounded explicitly reported overlap. Neither rotation nor repeated use extends the grant. Loss or compromise requires revocation and replacement; an expired key cannot renew itself.

Access sessions are short, with a five-minute maximum lease, clipped to parent/grant expiry. Refresh checks current authority and may continue autonomously while the grant remains valid. Runtime restart invalidates old leases. Durable jobs may outlive all connections, but every executing stage needs newly admitted authority; waiting releases access and keys. The calendar grant and lease defaults govern new automation; they do not change human settings.

### Lock, logout and revocation semantics

| Action or event | Required effect |
| --- | --- |
| Lock/log out of this session | End that session and its descendants; clear its private presentation state |
| Reconnect after session lock using a valid API key | May obtain a new independent session; a session lock does not revoke its root grant |
| Human logout or idle/absolute expiry | End that human session and attended descendants; disclose independently enabled automation |
| Revoke one key | End sessions derived from that key, refuse new admission and pause dependent jobs; other separately authorized keys remain scoped |
| Revoke a grant or all profile automation | Remove its usable unlock capability, revoke descendants and pause affected work |
| Lock this profile everywhere | Invalidate all profile sessions and suspend every automation unlock until fresh password-authorized resume |
| Resume a globally locked profile | Fresh password proof; show and explicitly select automation grants to reactivate within their original scope/end date |
| Password rotation/reset, recovery reset or profile deletion | Revoke all automation grants/unlock material; require re-enrollment if the profile remains |
| OS lock | End attended access; continue unattended work only if its enrollment explicitly permits it |
| Originating OS logout | Invalidate dependent human/attended sessions and descendants; do not revoke independent API grants |
| Unattended login eligibility or required credential facilities unavailable/unknown | Fence dependent work; another login or surviving user manager is insufficient |
| Last eligible logout | Fence private admission/effects, bounded runtime shutdown and custody release; no permanent grant revocation or profile-global suspension |
| Suspend/shutdown | Bounded best-effort preparation plus crash-safe reconciliation; fresh authority before resumed private output/effects |
| Runtime restart/upgrade | Discard live leases; authenticate and recheck protected state before resuming |
| Grant expiry | Refuse admission/refresh and pause work needing it until password-authorized renewal |

A key can open a new session after a single-session revocation; revoke the key/grant to remove that capability. Neither hiding a TUI screen nor switching profile is a global lock.

Revocation/lock is ordered against private-data release and mutation admission. Queued work rechecks before execution; local effects recheck at the authoritative commit boundary. A revocation acknowledgement identifies any earlier committed or externally uncertain effect. In-flight unsafe work follows declared settlement/reconciliation, without claiming rollback. Previously delivered data cannot be recalled.

### Mandatory CLI/TUI feature parity

Both interfaces independently invoke the same typed application operations and render their authoritative outcome. The TUI is not a command launcher; the CLI never imports or routes TUI screens. Naming extends the established config/app subjects without alternate API-key/token command aliases.

| Capability | CLI | TUI | Shared outcome |
| --- | --- | --- | --- |
| Select profile; password login; bounded resume | Commands and secure credential input | Profile picker and masked login | Same profile/session proof and expiry |
| Authenticate with an enrolled API key | Protected credential reference or explicit secret channel | Protected reference or masked key input | Same restricted session; no full-owner elevation |
| Request, inspect, approve or decline delegation | Typed request and decision commands | Pending-request inspection and decision controls | Exact connection/scope-bound consent |
| Create, list and inspect API keys/grants | Typed commands and JSON envelope | Key inventory and detail views | Same scope, expiry, state and last-used metadata; no secret re-display |
| Rotate, renew or change grant scope | Secure handoff and fresh proof | Secure handoff and fresh proof | Same overlap, generation and authorization rules |
| Revoke a key/grant or all automation | Explicit target and typed result | Equivalent targeted and bulk controls | Same revocation and affected-session/job result |
| List/inspect sessions and unattended access | Structured inventory | Session inventory with remaining access | Same identity, parent, expiry and capability facts |
| Lock/logout current session; revoke a selected session | Explicit scope | Explicit scope | Same invalidation and acknowledgement |
| Lock profile everywhere; password-authorized resume | Distinct profile-wide operation | Distinct profile-wide control | Same suspension and selected reactivation |

Key-authenticated CLI and TUI expose only authorized operations. Security administration does not become available because a particular screen can be opened. Human administration can revoke without expanding authority; enrollment, rotation, extension and global unlock require fresh proof. The password-authenticated human TUI may show the owner's data under its existing visibility decision; neither interface may export extra data through an agent session.

Parity acceptance exercises cross-interface transitions, not just inventories: create in CLI and inspect in TUI; rotate in TUI and reconnect from CLI/MCP; revoke in either and refuse the other; lock profile while another interface is operating; expire the human session while permitted automation resumes; and refuse administrative escalation from a key-authenticated TUI.

## Rationale

A durable grant answers whether unattended work is authorized; an API key authenticates its client; protected custody supplies decryption; a short session bounds present access. Separating them resolves the autonomous-resume requirement without extending a human login indefinitely. Shared application operations make the CLI/TUI parity requirement enforceable below presentation.

## Consequences

Scope amendment accepted 2026-10-03 under the operator's instruction: CLI/TUI parity applies to profile authentication, grants, sessions and work, and creates no runtime-management requirement. Remove the former runtime-management controls. Connection failures and authorization/custody state remain truthful application outcomes, without runtime health dashboards or service administration.

Cadrumo gains an optional delegated unlock path and a visible administration surface. It incurs credential-store portability, enrollment atomicity, revocation, generation and crash-recovery obligations. Background access is explicit and independently revocable.

Local API authentication cannot guarantee perpetual AEAT authentication, filing readiness or hostile same-user isolation. Accepted 2026-09-26 on the operator's instruction to continue the presented plan after the documentation handoff. Acceptance records the design; the plan separately records authorization for product implementation. It is not evidence that API keys or runtime behavior already work.
