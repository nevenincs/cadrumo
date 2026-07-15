---
tags:
  - "#adr"
  - "#aeat-auth-providers"
date: '2026-04-18'
modified: '2026-07-15'
related:
  - "[[2026-04-18-aeat-auth-providers-research]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-export-first-adr]]"
---

# auth-provider-abstraction-adr | (**status:** `accepted`)

## status

Accepted — 2026-04-18 (implementation reconciled 2026-07-15). The pluggable
`AuthProvider` abstraction is implemented: `AeatAuthenticator` is the concrete
certificate provider, alongside `ClaveMovilAuthProvider` and
`ClavePermanenteAuthProvider`. Cl@ve PIN remains a reserved catalogue slot, not
an implemented provider or engineering commitment. Supersedes the `Non-goals`
section of `2026-04-12-cert-auth-adr.md` (lines 83–84) which listed Cl@ve and
DNIe as out-of-scope. Builds on `2026-04-17-aeat-access-gate-adr.md` (the env-var
gate stays as the policy layer regardless of provider).

## context

`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/` today implements PKCS#12 certificate authentication as the sole AEAT Sede Electrónica login mechanism. The code models a `CertificateBundle`, a `LoadedCertificate`, four `CertificateBackend` enum values, and an `AeatSession` record four of whose fields are cert-specific. `AeatAuthenticator.__init__` unconditionally constructs a cert bundle.

The AEAT Sede accepts EIGHT distinct identification methods. Kent (our Spanish autónomo user) may have a digital certificate — or may have Cl@ve (most common for individuals who haven't gone through FNMT enrollment) — or both. Restricting the tool to cert auth excludes a large fraction of autónomos.

The research doc `.vault/research/2026-04-18-aeat-auth-providers-research.md` confirms:

- **Cl@ve Permanente** — DNI/NIE + password, SMS OTP only for activation/recovery and "top-level services." **For AEAT read paths this is a fully programmatic flow.** No SMS, no push, no phone. Playwright can drive it.
- **Cl@ve Móvil** — requires per-session push notification approval on a phone. Cannot be fully headless but is automatable up to the approval step.
- **Cl@ve PIN** — 24 h single-use PIN. Per-session friction similar to Cl@ve Móvil.
- **DNI electrónico** — smartcard + reader middleware. Platform-specific. Deferred.
- Once any provider authenticates, AEAT Sede returns uniform session cookies captured by Playwright `storage_state`. **Session replay is provider-independent.**

The project's export-first charter (#197) defers AEAT live writes to 1.0.0. Therefore the near-term auth requirement is **read-path authentication** across all four 0.x milestones that need live AEAT access (0.1.1, 0.3.0 import-from-aeat, 0.4.0 verify). For read paths, Cl@ve Permanente has no 2FA friction.

## decision

Generalise AEAT authentication from a single provider (certificate) to a
**pluggable `AuthProvider` abstraction**. The current implemented and reserved
inventory is:

| Provider | Priority | Automation envelope |
|---|---|---|
| `AeatAuthenticator` (`certificate`) | P0 — implemented | Fully headless |
| `ClavePermanenteAuthProvider` | P1 — implemented | Fully headless for read paths |
| `ClaveMovilAuthProvider` | P2 — implemented | Headless except per-session human approval on phone |
| `clave_pin` catalogue slot | Reserved, not implemented | No runtime provider |

`DniElectronicoAuthProvider` and `eIDASAuthProvider` are deferred to 1.x+ pending cross-platform smartcard middleware and EU-citizen use-case pressure.

### abstraction shape

```python
class AuthProvider(Protocol):
    """Provider-agnostic protocol for obtaining an AEAT-authenticated session."""

    kind: AuthProviderKind  # CERTIFICATE, CLAVE_PERMANENTE, or CLAVE_MOVIL

    async def authenticate(
        self,
        browser_session: BrowserSessionLike,
        settings: Settings,
    ) -> AeatSession:
        """Produce an authenticated context + session record."""
        ...

    def describe(self) -> AuthProviderDescription:
        """Name, kind, current configuration state, health."""
        ...

    async def verify(self, session: AeatSession) -> AeatLoginAssertion:
        """Re-probe that the session is still valid for this provider."""
        ...
```

### `AeatSession` generalisation

The existing session record splits into a **provider-agnostic core** and a **provider-specific detail**:

```python
class AeatSession(BaseModel, frozen=True):
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None
    identity_nif: str            # the taxpayer's NIF/NIE, obtained however
    provider_detail: CertificateSessionDetail | ClavePermanenteSessionDetail | ClaveMovilSessionDetail = Field(discriminator="kind")

    @property
    def provider_kind(self) -> AuthProviderKind:
        return self.provider_detail.kind
```

`provider_kind` is derived from the discriminated union rather than stored separately, eliminating the desync risk of two parallel fields. Cert-specific fields (`certificate_thumbprint`, `certificate_subject`, `handshake`) move to `CertificateSessionDetail`. Other providers have their own detail types.

### browser session generalisation

```python
class BrowserSessionLike(Protocol):
    async def create_context(
        self,
        provisioner: BrowserContextProvisioner | None = None,
    ) -> BrowserContextLike:
        ...
```

`BrowserContextProvisioner` is a callable that knows how to decorate a Playwright `new_context(**kwargs)` call — for cert providers it injects `client_certificates=[...]`; for Cl@ve providers it is a no-op at `create_context` time (Cl@ve auth happens after context creation via form drive).

### `AeatAccessGate` stays provider-agnostic

The three env vars already there (`AEAT_ALLOW_LIVE_READ_OPT_IN`, `AEAT_LIVE_READ_ENABLED`, and the write-side variants per #117/#197) remain the policy layer. Gate enforcement is unchanged. Provider selection is orthogonal.

### CLI surface (superseded shape reconciled)

```
aeat config auth providers             # implemented + reserved catalogue entries
aeat config auth configure --provider certificate|clave_movil|clave_permanente
aeat config auth status
aeat config auth test
aeat config auth clear
```

The later accepted `2026-05-12-cli-workflow-redesign-config-auth-shape-adr`
supersedes the former top-level `aeat auth` grammar and is the authority for the
operator-facing catalogue and verbs.

## scope

**IN scope for this ADR:**
- Generalise `AeatSession`, `AeatAuthenticator`, `BrowserSessionLike.create_context`, and the health/doctor/submit surfaces
- File per-provider EPIC with cert-provider reframe + Cl@ve Permanente + Cl@ve Móvil as children
- Update existing cert-auth ADR to remove the Cl@ve non-goal wording (supersession reference only)
- Session storage_state remains per-provider (different `storage_state_path` per provider for a given user)

**OUT of scope:**
- `DniElectronicoAuthProvider` — deferred to 1.x+ pending smartcard tooling decision
- `eIDASAuthProvider` — deferred; no use case in the Kent persona
- Multi-provider session merging ("login with cert AND Cl@ve in one run") — pick one per session
- Provider switching mid-session — re-login required when changing provider

## consequences

**Positive:**

- Kent without a FNMT certificate can use the tool end-to-end. Largest single unlock of the user base.
- The read-path auth unblocking (Cl@ve Permanente) does not need SMS OTP or phone — zero additional friction compared to cert.
- The abstraction cleanly slots future providers (DNI-e, eIDAS) behind the same protocol.
- Session replay and the `AeatAccessGate` are already provider-agnostic; this ADR preserves those correct existing abstractions.
- The export-first charter is unchanged; multi-provider auth does not require the write-path to ship.

**Negative / cost:**

- Breaking type change on `AeatSession`, `BrowserSessionLike.create_context`, and downstream consumers (`aeat.adapters.outbound.aeat.browser`, `aeat.adapters.outbound.aeat.export`, `aeat.application.workflow` stubs).
- Test matrix grows: each provider needs unit + live tests; `live_read` marker now applies per provider.
- Cl@ve Permanente password storage is a new secret surface (treat like the cert passphrase: env var, optional OS keyring).
- Cl@ve Móvil UX requires a polling + "approve on your phone" prompt that is new to the CLI.

**Neutral:**

- `LoadedCertificate` stub in `aeat.adapters.outbound.aeat.export._protocols` and `aeat.application.workflow._protocols` still needs the rebase-swap per the existing TODO comments; this ADR is a good anchor to do it.

## rollout

- The session-shape refactor and the certificate, Cl@ve Permanente, and Cl@ve
  Móvil providers are implemented behind the shared protocol.
- `provider_detail.kind` is the sole stored provider-kind authority for session
  and assertion records; `provider_kind` is a read-only projection.
- Cl@ve PIN remains reserved unless a later accepted ADR and implementation
  promote it; the reservation alone is not an open engineering gap.

## alternatives considered

1. **Keep cert-only; Cl@ve users are out of scope.** Rejected: excludes a large portion of Spanish autónomos who have only Cl@ve, for no defensible technical reason.
2. **Ship only Cl@ve Permanente; drop cert support.** Rejected: cert code is substantial, working, and needed for autónomos who have invested in FNMT infrastructure. Also, cert is the only provider that supports the live-write path without elevation in 1.0.0.
3. **Abstract at the BrowserSession level, not the AuthProvider level.** Rejected: BrowserSession already *is* auth-agnostic; the cert-shape lives in the session record and the authenticator. Abstracting a layer higher (the authenticator itself) is the right seam.
4. **One auth provider per Settings profile instance — no pluggability at runtime.** Rejected: prevents Kent from having cert on one machine and Cl@ve on another while sharing `env/.env` via secret store indirection.

## 2026-04-27 amendment — read-only scope clarification

Issue `#432` permanently forbids live AEAT submission. This ADR therefore
remains valid only for provider-agnostic authentication, session acquisition,
and read-path access.

- Auth providers may support sede walking, notifications, status/history reads,
  and past-filing import.
- Auth providers do not preserve, imply, or enable a future live-submit path.
- Any earlier wording that deferred live writes to 1.0.0 is superseded by the
  permanent-forbid policy.
