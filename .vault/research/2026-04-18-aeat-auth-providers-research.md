---
tags:
  - "#research"
  - "#aeat-auth-providers"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-12-cert-auth-research]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
---

# aeat-auth-providers-research

Research for generalising AEAT authentication from single-provider (PKCS#12 certificate) to multi-provider (certificate + Cl@ve Permanente + Cl@ve Móvil + Cl@ve PIN + DNI electrónico). Supersedes the `Non-goals` in `2026-04-12-cert-auth-adr.md` which listed Cl@ve and DNIe as out-of-scope.

## current state of `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/`

### cert-specific surface (what exists today)

| Surface | File:line | Cert-coupled? |
|---|---|---|
| `AeatAuthenticator` facade | `_authenticator.py:239` | Yes — unconditionally builds a `CertificateBundle` in `__init__` |
| `AeatSession` record | `_authenticator.py:127` | Yes — fields `certificate_thumbprint`, `certificate_subject`, `certificate_nif`, `handshake` |
| `AeatLoginAssertion` | `_authenticator.py:84` | Yes — fields `handshake_success`, `certificate_recognised`, `parsed_nif`, `parsed_subject` |
| `BrowserSessionLike.create_context(cert: LoadedCertificate \| None)` | `_authenticator.py:221` | Yes — parameter typed to cert class |
| `_CertBackend` ABC | `_certificate_backends/_base.py:12` | Yes — both methods require `LoadedCertificate` |
| `CertificateBackend` enum | `certificate.py:151` | Yes (by name) — 4 variants: `PLAYWRIGHT_CONTEXT`, `USER_DATA_DIR`, `MTLS_PROXY`, `HTTPX_FALLBACK` |
| `AeatAccessGate` | `_gate.py:83` | **No** — provider-agnostic; just env-var read/write gates |
| Session TTL `AEAT_SESSION_IDLE_TTL = 18 min` | `_authenticator.py` | Per-session TTL, portable across providers |

### what is already abstract

- **`BrowserSessionLike` protocol** — auth-agnostic; any auth mechanism can produce a `BrowserContext`.
- **`BrowserPageLike`, `BrowserResponseLike`** — purely navigation-shaped.
- **`AeatAccessGate`** — policy layer over env vars.
- **`storage_state_path`** on `AeatSession` — Playwright cookies+localStorage JSON; once *any* provider authenticates, storage_state captures the session cookies uniformly.

### what is cert-coupled and must be generalised

- `AeatSession` four cert-specific fields (`certificate_*`, `handshake`)
- `AeatAuthenticator.__init__` bundling construction
- `BrowserSessionLike.create_context(cert=...)` parameter type
- `verify_login()` assertion fields
- `_MARKER_ATTR = "_aeat_certificate_thumbprint"` on the context

---

## external research — AEAT identification methods

The AEAT Sede Electrónica accepts EIGHT identification methods per [sede.agenciatributaria.gob.es/Sede/identificacion-digital.html](https://sede.agenciatributaria.gob.es/Sede/identificacion-digital.html):

| # | Method | Factor(s) | Requires mobile? | Automatable? |
|---|---|---|---|---|
| 1 | **Certificado electrónico** | PKCS#12 file + passphrase | No | **Yes** — current implementation |
| 2 | **DNI electrónico** | Smartcard + PIN via reader | No (needs reader) | Partial — requires smartcard middleware |
| 3 | **Cl@ve Móvil** | Cl@ve app push or QR | **Yes** | Partial — requires human tap on phone |
| 4 | **Cl@ve Permanente** | DNI/NIE + password; SMS OTP for "top-level services" | Only for elevated operations | **Yes** for read paths |
| 5 | **Cl@ve PIN** | 24 h single-use PIN requested per session | Yes (PIN arrives via app or SMS) | Poorly — 24 h window, per-session |
| 6 | **Número de referencia** | Reference number from prior IRPF filing | No | Depends on scope (IRPF campaign only) |
| 7 | **DNI/NIE + datos de contraste** | DNI/NIE + personal data (validity date, etc.) | No | Yes but read-only scope |
| 8 | **eIDAS (EU citizens)** | Foreign EU member state eID | Varies | Out of scope |

Additional special-purpose methods: CSV codes (per-document), TOKEN (phone representation — for gestores).

Sources:
- [AEAT Sede: Identificación electrónica](https://sede.agenciatributaria.gob.es/Sede/identificacion-digital.html)
- [Cl@ve: What is Cl@ve](https://clave.gob.es/en/clave/que-es)
- [Cl@ve Permanente procedures](https://clave.gob.es/en/clave-permanente/procedimientos)
- [Cl@ve Móvil usage](https://clave.gob.es/en/clave-movil/uso-clave-movil)

### Cl@ve Permanente details

From the official `clave.gob.es` procedures page:

- **Activation (one-time):** DNI/NIE + email + activation code → SMS OTP → user creates a password
- **Routine login:** DNI/NIE + password only
- **SMS OTP is required for:** activation, password recovery, and "top-level services"
- **Password policy:** ≥8 chars, upper + lower + digit + special; expires after 2 years (forced renewal)
- **Session lifetime:** not publicly specified; observed AEAT Sede session idle TTL ≈ 18 minutes

**Critical corollary for this project:** for AEAT *read paths* (expedientes, justificantes, inbox, datos-fiscales), Cl@ve Permanente login is a headless-automatable flow: no SMS, no push, just form submission. AEAT *write paths* (live submission) would hit the SMS-OTP elevation — but the charter #197 defers live writes to 1.0.0 anyway, so this limitation does not constrain the near-term roadmap.

### Cl@ve Móvil details

- **Mechanism:** user identifies with DNI/NIE on the login page; Cl@ve backend dispatches a push notification to the Cl@ve app on their phone OR displays a QR code to scan; user approves the request on the phone.
- **Additional factors on the phone:** PIN, biometric, or face ID (enforced by the app).
- **Automatable?** The landing URL is automatable; the approval is NOT. The tool can navigate to the login page, supply DNI/NIE, wait for the user's approval on their phone, then observe the redirect back to the relying party.
- **UX pattern:** human-in-the-loop per-session; highest security, highest friction.

### Cl@ve PIN details

- Per-session 24 h single-use PIN delivered via app or SMS.
- Intended for sporadic access by users who don't have Cl@ve Permanente.
- Similar automation envelope to Cl@ve Móvil — tool can drive the DNI/NIE entry; user must obtain and enter the PIN.

### DNI electrónico

- Requires physical smartcard + PIN + card reader on the host machine.
- TLS client cert is the smartcard's embedded cert; conceptually close to the PKCS#12 flow but reader middleware is platform-specific (Windows Smart Card API, PC/SC on Linux, macOS keychain).
- Out of scope for 1.x; re-visit when cross-platform reader tooling stabilises.

---

## AEAT Sede session behaviour (post-login, any provider)

Once *any* provider successfully authenticates, AEAT Sede sets session cookies on the Playwright `BrowserContext`. The Playwright `storage_state` JSON captures these cookies + localStorage, so **session replay across providers is uniform** — the `storage_state_path` field on `AeatSession` works identically whether the original auth was cert or Cl@ve.

Observed behaviours on the real portal:
- Idle session TTL ≈ 18 minutes (matches the current hardcoded `AEAT_SESSION_IDLE_TTL`)
- Session cookie is HttpOnly + Secure
- No refresh endpoint — re-authentication is required after TTL expiry
- Live-write operations may prompt for re-authentication at a higher assurance level ("IAL-2" equivalent) — Cl@ve Permanente sessions will encounter the SMS-OTP elevation at that boundary; cert sessions do not

---

## downstream-consumer inventory

| Consumer | Coupling | Generalisation effort |
|---|---|---|
| `aeat.adapters.outbound.aeat.browser.session.BrowserSession.create_context(cert=...)` | Typed parameter `LoadedCertificate \| None` | Change signature to accept a `BrowserContextProvisioner` (new protocol) |
| `cli/submission/submit.py` | Imports `CertificateError`, `CertificateHealthSeverity`, `health` | Health surface must become per-provider; cert remains one of several |
| `cli/doctor.py` | Cert rows in health table | Add per-provider rows |
| `aeat.adapters.outbound.aeat.export._protocols.LoadedCertificate` (stub) | Local stub with rebase-swap comment | Swap to the new provider-agnostic session type when #8 closes |
| `aeat.application.workflow._protocols.CertificateBundleProtocol` | Named for cert | Generalise to `AuthProviderBundle` |

---

## supersession of prior non-goals

The `2026-04-12-cert-auth-adr.md` lists (line 83-84):

> Non-goals:
> - Cl@ve (user + PIN) authentication
> - DNIe (Spanish national ID card) authentication

This research **supersedes** those non-goals for Cl@ve Permanente and Cl@ve Móvil. DNIe remains deferred. The new ADR (drafted separately) records the scope change and the rationale: Cl@ve Permanente is the clearest second programmatic path, opening the tool to autónomos who do not have a PKCS#12 cert.

---

## open questions flagged for the ADR

1. **Does AEAT Sede's Cl@ve-authenticated session return the same cookies as a cert-authenticated one?** — to verify empirically with a live login test; expected yes because cookies are set by AEAT, not by the IdP.
2. **Can a single user combine providers within a run?** — cert for some operations + Cl@ve Permanente for others — probably not useful; pick one per session.
3. **Storage state portability across providers** — if Kent authenticates via Cl@ve Permanente on Monday and cert on Tuesday, do we need separate storage_state files? Probably yes (different auth tokens).
4. **Where does the Cl@ve Permanente password live?** — same treatment as the cert passphrase: env var, optionally backed by OS keyring. Must NOT end up in `env/.env` committed anywhere.
5. **Audit trail** — the existing `LiveSubmitAuditRecord` captures the auth env state; it should record which provider was used. Minor schema addition.
