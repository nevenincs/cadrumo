---
tags:
  - '#adr'
  - '#aeat-access-gate'
date: 2026-04-17
modified: '2026-07-17'
title: "Live AEAT Access Blocker & Verification Gate"
related:
  - "[[2026-04-17-aeat-access-gate-research]]"
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-16-submission-safety-sweep-adr]]"
  - '[[2026-07-16-protected-browser-certificate-auth-adr]]'
---

# ADR: Live AEAT Access Blocker & Verification Gate | (**status:** `accepted`)

## Status
Accepted — 2026-04-17. Implements GitHub issue #167.

## Context

The related access-gate research establishes that the project has a
working PKCS#12 cert loader (#8), a pre-expiry gate (#94), and a
nine-point live-write safety gate (#116 R1–R6 + #117). What it does
**not** yet have is:

1. A single entry point that binds the cert, the browser, and the
   write-gate together for future remote-read work to depend on.
2. A protected-resource **identity assertion**: proof that the configured
   certificate identity can reach the exact authenticated AEAT resource
   (parsed NIF from the certificate subject + successful canonical browser
   navigation).
3. Cert propagation into the Playwright context. The current
   `BrowserSession.create_context()` accepts an `auth_backend` arg
   and discards it (stub from #8). The certificate must instead be supplied
   through construction-time Playwright `client_certificates` context kwargs.
4. A read-side gate usable by future live-read call-sites
   (#168–#171 are the next wave), mirroring the write-gate already
   in place.

The user mandated that any architectural regression in the auth /
write layer is in scope for this PR, and that correct gating at CLI,
API, and code-path level is non-negotiable. The audit concluded the
write gate is solid; the fragmentation sits on the read / browser-
wiring side.

## Decision

### D1 — `AeatAuthenticator` facade in `cadrumo.adapters.outbound.aeat.auth`

New class `AeatAuthenticator` lives in
`src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py` and is re-exported from
`cadrumo.adapters.outbound.aeat.auth`. It owns the composition of:

- `Settings` for non-credential policy and typed
  `ActiveCertificateCredentials` selected by application orchestration; no
  per-call auth inputs.
- `CertificateBundle` / `LoadedCertificate` (via the existing
  `load_certificate` + `health` entry points; **not re-implemented**).
- A `BrowserSessionFactory` supplied by application orchestration for async
  Playwright operations. Constructor omission is valid only for synchronous
  certificate helpers.
- A single `_lock: asyncio.Lock` guarding concurrent
  `authenticate()` calls within a process.

The surface is intentionally narrow:

```python
class AeatAuthenticator:
    """Single entry point for live AEAT access.

    Owns cert loading, health evaluation, Playwright-context wiring,
    and login-assertion verification. Future remote-read modules
    depend on this class rather than re-implementing the wiring.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        credentials: ActiveCertificateCredentials,
        browser_session_factory: BrowserSessionFactory | None = None,
    ) -> None: ...

    def load_certificate(self) -> LoadedCertificate: ...
    def health(self, *, now: datetime | None = None) -> CertificateHealth: ...
    async def authenticate(self) -> AeatSession: ...

    async def reauthenticate(
        self,
        session: AeatSession,
    ) -> AeatSession: ...

    async def verify(self, session: AeatSession) -> AeatLoginAssertion: ...

    def extract_nif_from_subject(
        self,
        cert: LoadedCertificate,
    ) -> str: ...

    async def close(self) -> None: ...
```

`reauthenticate(session)` is the recovery path when a downstream
call sees a 401 / 403 or `verify()` returns an invalid canonical
protected-resource assertion. Semantics:

- Drops the current Playwright context and `storage_state`.
- Re-runs `authenticate()` with the same certificate identity and canonical
  protected-resource assertion.
- Returns a new `AeatSession` with a fresh `authenticated_at` +
  `idle_deadline`.
- Enforces a **hard cap of one retry per downstream call-site** to
  avoid burning AEAT anti-bot signals. Callers that observe a
  failed `verify()` after `reauthenticate()` must raise
  `AeatSessionExpiredError` upwards, not loop.
- Raises `CertificateExpiredError` directly if the cert itself has
  expired since the original `authenticate()`; the old session is
  discarded regardless.

Behavioural contract:

- `load_certificate()` / `health()` are thin forwarders to the existing
  certificate functions, parameterised by `self.settings`. They let callers
  use the authenticator without Playwright (for example, the doctor row and
  CLI certificate checks).
- `authenticate()` is the **only** entry point that drives
  Playwright. It loads the cert (raising on expiry / missing env
  var), contributes `client_certificates` while constructing the
  `BrowserContext`, and proves the session by navigating to
  `https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`.
- `verify()` uses that same fixed navigation. Success requires a successful
  response and the exact final scheme, host, and path; it is not configurable
  per call. The returned `AeatLoginAssertion` also carries the NIF and subject
  derived from the loaded certificate.
- `close()` releases the context + browser cleanly.

### D2 — `AeatSession` pydantic record

New record in `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`:

```python
class AeatSession(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True,
    )

    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None
    identity_nif: str
    provider_detail: CertificateSessionDetail

    def is_stale(self, now: datetime | None = None) -> bool: ...
```

Fields:

- `provider_detail.certificate_thumbprint` — SHA-256 hex of the cert's DER
  encoding. Ties the session to a specific bundle.
- `provider_detail.certificate_subject` — RFC-4514 subject DN.
- `identity_nif` — NIF extracted from the cert subject by
  `extract_nif_from_subject()`. See D5 for the parser.
- `provider_detail.protected_resource_url` — the fixed protected resource
  whose successful exact navigation established this certificate session.
- `authenticated_at` — UTC timestamp of `authenticate()` return.
- `idle_deadline` — timezone-aware UTC timestamp beyond which the
  session MUST be re-authenticated before further use. Derived as
  `authenticated_at + AEAT_SESSION_IDLE_TTL`. The TTL is a
  module-level constant in `cadrumo.adapters.outbound.aeat.auth._authenticator`
  (`AEAT_SESSION_IDLE_TTL = timedelta(minutes=18)`); **not a new env
  var** (per the anti-fragmentation mandate — AEAT's observed idle
  window is ~20 minutes and 18 minutes gives a safety margin, but
  the value is a code-level constant, not an operator knob).
- `storage_state_path` — Playwright `storage_state` JSON location
  (or None if the caller chose not to persist).

`is_stale(now)` returns `now > self.idle_deadline`; default `now`
is `datetime.now(UTC)`. The session carries **no secret material**.
It is safe to log, and its `model_dump()` / `model_dump_json()`
surfaces are safe for the audit log and doctor row.

#### Cert-expires-mid-session semantics

If the underlying PKCS#12 cert expires while a session is open, the
session record is **not mutated**. Any subsequent call through the
authenticator (`authenticate()`, `reauthenticate()`, `verify()`)
loads the cert afresh and raises the existing
`CertificateExpiredError` from that call — never from an in-flight
`AeatSession`. Downstream code therefore never needs to inspect a
session record to decide whether the cert is still valid; it just
has to call the authenticator again and let the error hierarchy
surface the failure.

### D3 — `AeatLoginAssertion` pydantic record

A separate record for the verification *act* rather than ongoing
state:

```python
class AeatLoginAssertion(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    target_url: str
    is_valid: bool
    identity_nif: str | None
    status_code: int
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None
    assertion_detail: CertificateLoginAssertionDetail
```

- `target_url` is always
  `https://www6.agenciatributaria.gob.es/wlpl/TEWV-CORE/ResumenVlt`.
- `assertion_detail.response_successful` records Playwright's response-success
  signal, while `assertion_detail.final_url` must have the exact canonical
  scheme, host, and path.
- `identity_nif` / `assertion_detail.parsed_subject` are from the cert itself, not from
  scraped AEAT HTML (HTML surface is too volatile; the cert subject
  is authoritative and immutable per bundle).
- `is_valid` — successful response, exact canonical final location, and
  `identity_nif is not None`. Predicate field name (not a verb);
  downstream code reads `if assertion.is_valid: ...`.
- When `is_valid` is False,
  callers may invoke `AeatAuthenticator.reauthenticate()` **once**
  and re-verify; a second consecutive failure MUST raise
  `AeatSessionExpiredError` upwards rather than loop.

**Why parse the NIF from the cert, not the portal HTML?** AEAT's
post-auth chrome rotates between campaigns. The cert's subject DN
cannot rotate — it's cryptographically bound to the bundle the
operator supplied. This gives a **mathematically verified** identity
assertion (the audit's phrase from the issue brief) without a
fragile HTML scraper.

### D4 — `AeatAccessGate` unified read+write precondition

The provider-agnostic gate lives in `src/cadrumo/core/access_gate/__init__.py`
and is re-exported from `cadrumo.core`:

```python
@dataclass(frozen=True, slots=True)
class AeatAccessGate:
    settings: Settings

    def require_live_read(self) -> None: ...
    def require_live_write(self) -> None: ...
    def snapshot_env(self) -> AeatGateEnvSnapshot: ...
```

Behaviour:

- `require_live_read()` — raises `AeatLiveReadNotEnabledError` when
  `AEAT_LIVE_TESTS_ENABLED != "1"`. Usable from the existing
  per-test `pytest.skip` sites (they keep their skip logic; the
  gate merely gives non-test callers the same check). Also usable
  from future CLI live-read commands (#168 history fetcher etc.).
- `require_live_write()` — raises the *existing* error taxonomy:
  `AeatLiveSubmitNotEnabledError` when `aeat_live_submit_enabled`
  is False, `AeatPytestLiveWriteRefusedError` when
  `PYTEST_CURRENT_TEST` is present in `os.environ`. **This is a
  defensive helper**, not a replacement for the existing inline
  checks in `SubmissionEngine._submit_with_transport()` — R5 demands
  belt-and-braces; we keep both.
- `snapshot_env()` — returns `AeatGateEnvSnapshot`, a frozen pydantic
  record of `{aeat_live_tests_enabled, aeat_live_submit_enabled,
  pytest_current_test_set}`. The engine *prefers* threading the
  snapshot through to `_audit.append_record()`, but `_audit.py`
  **retains its own fallback re-read** of the same three env vars
  — that fallback is R6 defence and is not deleted.

**Non-injection rule (R5 preservation):** the gate is **always
constructed inline from `Settings` at the engine call-site**. It is
never injected via `SubmissionEngine.__init__`, never stored on
`self`, never passed as a constructor kwarg. A `gate=` kwarg on
`SubmissionEngine` is explicitly forbidden. This preserves R5's
"no substitutable dependency on the write-gate" property: a test
cannot swap the gate for a no-op because there is no seam to swap
through.

**Cross-cutting home rationale:** `cadrumo.core.access_gate` lives in the core
policy layer rather than the outbound auth or export adapters because the gate
serves both live reads and the permanent live-write refusal. Outbound readers
import `AeatAccessGate` from the top-level `cadrumo.core` re-export per the
project's public-boundary convention.

### D5 — NIF extraction from FNMT cert subject

FNMT *persona física* certs always carry the taxpayer identifier in
the subject's `serialNumber` attribute (OID 2.5.4.5), commonly
formatted either as `IDCES-NNNNNNNNL` or bare `NNNNNNNNL`. The CN
typically repeats it, but `serialNumber` is canonical. The parser:

```python
_SERIAL_PREFIX_RE = re.compile(r"^IDCES-", re.IGNORECASE)
_DNI_RE = re.compile(r"^[0-9]{7,8}[A-Z]$")
_NIE_RE = re.compile(r"^[XYZ][0-9]{7}[A-Z]$")

def extract_nif_from_subject(cert: LoadedCertificate) -> str:
    ...  # returns normalised uppercase NIF (DNI or NIE);
         # raises CertificateNifParseError on shape mismatch
```

**DNI vs NIE scope**: the parser accepts both DNI (`[0-9]{7,8}[A-Z]`)
and NIE (`[XYZ][0-9]{7}[A-Z]`). NIE holders (residents with a
*Número de Identidad de Extranjero*) can be issued FNMT *persona
física* certs with their NIE in the `serialNumber` attribute; the
project's target user is an autónomo, who may legally be either.
Any other shape — e.g. CIF for *persona jurídica* certs — is
**rejected** via `CertificateNifParseError`; this project
explicitly does not support legal-entity certificates (out of
scope for autónomos).

A new `CertificateNifParseError(CertificateError)` is added to the
existing error hierarchy. Unit tests generate self-signed FNMT-shaped
subjects at runtime (using `cryptography.x509.Name` with an explicit
`SERIAL_NUMBER` attribute) — same pattern the cert tests already use.
Tests cover: bare DNI, `IDCES-`-prefixed DNI, NIE, legal-entity
CIF (rejected), empty subject (rejected), missing `serialNumber` OID
(rejected).

### D6 — Fix the BrowserSession cert-propagation regression

`src/cadrumo/adapters/outbound/aeat/browser/session.py:BrowserSession.create_context()`:

- Replace the dormant `auth_backend` parameter with the typed
  `BrowserContextProvisioner` seam.
- `CertificateContextProvisioner` builds Playwright `client_certificates`
  kwargs for the exact protected AEAT origin. `BrowserSession.create_context()`
  merges those kwargs **before** `browser.new_context(**context_kwargs)`.
- No out-of-band context attribute participates in authentication. Certificate
  identity remains in the typed session detail and encrypted persisted-state
  metadata.
- Unit tests assert the exact context kwargs and canonical protected-resource
  navigation contract.

This is **a small, targeted fix, not a rewrite**. The evasion /
profile / site-health wiring in `BrowserSession` is untouched.

### D7 — Prefer engine-provided env snapshot; retain audit-side fallback

The engine builds one `AeatGateEnvSnapshot` at gate-check time and
passes it into every `_audit.append_record(...)` call. This
tightens the correspondence between "what the engine saw" and
"what got logged" in the common path.

**`_audit.py:77-82`'s own env re-read is NOT deleted.** It is
retained as a last-mile R6 defence: if any future call-site
invokes `append_live_submit_audit()` without threading a snapshot
through, the audit log still records the env-var state rather
than silently dropping the field. This defence in depth is
deliberate per R6's intent that every successful live write
**must** produce a complete audit record regardless of caller
discipline.

The audit JSONL schema is unchanged: the same three keys
(`aeat_live_tests_enabled`, `aeat_live_submit_enabled`,
`pytest_current_test_set`) appear in exactly the same shape.
Readers of `.aeat/live-submit-audit.log` are unaffected.

### D8 — Document `AEAT_LIVE_SUBMIT_ENABLED` absence in `env/.env.example`

Add a clearly-labelled comment block to `env/.env.example`:

```
# ── Live-write gate (R3 charter — issue #116) ─────────────────────
# AEAT_LIVE_SUBMIT_ENABLED is INTENTIONALLY NOT LISTED here.
# Setting it persists a value into a dotfile that can be loaded by
# test runs, violating R3. Export it only in an interactive shell,
# and only immediately before a real filing event. Unset it after.
# Authoritative reference: .vault/adr/2026-04-16-submission-safety-sweep-adr.md
# and GitHub issue #116 ("Live-AEAT-write safety charter").
```

No new keys are added. The block exists so a reader of `.env.example`
understands the omission is deliberate, and can grep their way from
the comment to the charter.

### D9 — Live test: single `@pytest.mark.live` item

A live test `src/cadrumo/adapters/outbound/aeat/auth/tests/test_authenticator_live.py`:

- Marker: `@pytest.mark.live` (the only registered marker; the
  handover prompt's `live_read` / `domain_aeat_remote` are **not**
  valid under `--strict-markers`).
- Skip semantics (matching existing live tests):
  - Skip when `AEAT_LIVE_TESTS_ENABLED != "1"`.
  - Skip when `AEAT_CERTIFICATE_PATH` / `AEAT_CERTIFICATE_PASSWORD_SECRET`
    are unset.
- Exercises:
  - `AeatAuthenticator(Settings()).health()` returns OK severity.
  - `extract_nif_from_subject()` returns a valid NIF shape.
  - Under a real Playwright run,
    `await authenticator.authenticate()` returns an `AeatSession`,
    and `await authenticator.verify(session)` returns
    `AeatLoginAssertion(is_valid=True)`.
- Zero mocks, patches, fakes (R5 + `tests/conftest.py` enforcement).
- Clean up with `async with authenticator` or explicit
  `await authenticator.close()`.

### D10 — Workflow / submission integration

`SubmissionEngine._submit_with_transport()` is **not rewritten**.
The nine-point gate stays as-is; we only change:

- `_engine.py:214-216` constructs a local `AeatAccessGate` from
  `self.settings` (no `self.gate`, no kwarg injection) and calls
  `gate.snapshot_env()` to build the record passed into
  `_audit.append_record(...)`.
- `_audit.append_record` signature accepts the snapshot; the JSONL
  schema is **unchanged** (same three keys); `_audit.py`'s own
  env re-read fallback remains in place (see D7).
- `_engine.py:207-212`'s inline gate checks are **byte-for-byte
  unchanged**. The gate only owns the *env-snapshot dict build*,
  not the gate-check sequencing.
- `SubmissionEngine.__init__` gains **no** new parameters. A
  `gate=` kwarg is explicitly forbidden (see D4 non-injection
  rule).
- No change to `_confirm.py`, `_preflight.py`, CLI flag handling.

### D11 — Error surface additions

All added to the `cadrumo.core.errors`-rooted hierarchy via
`cadrumo.adapters.outbound.aeat.auth`:

- `AeatLiveReadNotEnabledError(AeatError)` — raised by
  `AeatAccessGate.require_live_read()` when `AEAT_LIVE_TESTS_ENABLED`
  is not `"1"`.
- `AeatLoginAssertionError(CertificateError)` — raised by
  `verify()` when the assertion cannot be produced (network
  error, page missing before Playwright can parse it).
- `AeatSessionExpiredError(CertificateError)` — raised when an
  `AeatSession.is_stale()` check trips, or when a single
  `reauthenticate()` attempt still yields an invalid canonical
  protected-resource assertion. Downstream callers propagate the
  error upwards rather than loop on reauthenticate.
- `CertificateNifParseError(CertificateError)` — raised by
  `extract_nif_from_subject()` when the subject DN carries no
  recognisable NIF.

Existing errors are not renamed or re-homed.

## Consequences

### Positive

- Single entry point for all future remote-read modules: they depend
  on `AeatAuthenticator` instead of rewiring cert + browser + env
  checks per call-site.
- Verifiable identity assertion: cert-derived NIF plus successful navigation
  to the exact protected AEAT resource, captured in a frozen pydantic record.
- Closes the `BrowserSession` regression that would have blocked
  any real Playwright-based live read with a cert.
- Adds a symmetric read-side gate mirroring the existing write
  gate, reducing boilerplate across live tests and future CLI
  commands.
- Centralised env snapshot ends the audit-log / engine drift risk.

### Negative / accepted

- `BrowserSession.create_context(auth_backend=...)` is replaced by the typed
  provisioner seam. The old parameter was unused, and no compatibility alias
  remains.
- `AeatAuthenticator` holds a Playwright `Browser` + `BrowserContext`
  across `authenticate()` and `close()`. Callers must use it as an
  async context manager or wrap the call-site in a `try/finally`.
  The class raises `AeatLoginAssertionError` on misuse (double
  `authenticate()` without close) rather than silently re-opening.
- The live test adds ~90 seconds to a full live run (Playwright
  spin-up + navigation). It is gated on the existing env var set
  and skipped by default, so standard unit runs are unaffected.
- Session idle TTL is a hard-coded constant (18 minutes). If AEAT
  adjusts its idle window we will follow up with a focused change
  — no env var is introduced for this knob (keeping the operator
  surface narrow).

## Non-goals (restated)

- No re-home of the certificate loader.
- No new subpackage (per user's anti-fragmentation mandate;
  everything lands inside `cadrumo.adapters.outbound.aeat.auth`).
- No new env vars.
- No changes to the R1–R6 write-gate semantics; only the env
  snapshot re-read is consolidated.
- No Cl@ve / DNIe.
- No renewal automation beyond the existing pre-expiry gate.

## Operator runbook (delta)

When a future live-read module fails:

1. `aeat doctor` should already surface the cert health row. If
   the new authenticator is involved, the doctor row gains a
   "Live access gate" sub-row (OK / WARN / MISSING) sourced from
   `AeatAccessGate.snapshot_env()`.
2. If the canonical protected-resource assertion fails, check certificate
   registration at FNMT / AEAT and confirm the final URL has the exact expected
   scheme, host, and path.
3. If `parsed_nif` does not match the expected taxpayer NIF, the
   operator has the wrong cert configured. Re-check
   `AEAT_CERTIFICATE_PATH`.
