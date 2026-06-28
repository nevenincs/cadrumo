---
tags:
  - "#adr"
  - "#aeat-access-gate"
date: 2026-04-17
modified: '2026-04-17'
title: "Live AEAT Access Blocker & Verification Gate"
related:
  - "[[2026-04-17-aeat-access-gate-research]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-16-submission-safety-sweep-adr]]"
---

# ADR: Live AEAT Access Blocker & Verification Gate

## Status
Accepted — 2026-04-17. Implements GitHub issue #167.

## Context

See `[[2026-04-17-aeat-access-gate-research]]`. The project has a
working PKCS#12 cert loader (#8), a pre-expiry gate (#94), and a
nine-point live-write safety gate (#116 R1–R6 + #117). What it does
**not** yet have is:

1. A single entry point that binds the cert, the browser, and the
   write-gate together for future remote-read work to depend on.
2. A post-handshake **identity assertion**: proof that the cert AEAT
   accepts at TLS belongs to the expected taxpayer (parsed NIF from
   cert subject + reachable post-auth portal).
3. Cert propagation into the Playwright context. The current
   `BrowserSession.create_context()` accepts an `auth_backend` arg
   and discards it (stub from #8). Any caller that wires the backend
   correctly is blocked by the missing thumbprint marker on the
   context.
4. A read-side gate usable by future live-read call-sites
   (#168–#171 are the next wave), mirroring the write-gate already
   in place.

The user mandated that any architectural regression in the auth /
write layer is in scope for this PR, and that correct gating at CLI,
API, and code-path level is non-negotiable. The audit concluded the
write gate is solid; the fragmentation sits on the read / browser-
wiring side.

## Decision

### D1 — `AeatAuthenticator` facade in `aeat.adapters.outbound.aeat.auth`

New class `AeatAuthenticator` lives in
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` and is re-exported from
`aeat.adapters.outbound.aeat.auth.__init__`. It owns the composition of:

- `Settings` (the sole input; no per-call args).
- `CertificateBundle` / `LoadedCertificate` (via the existing
  `load_certificate` + `health` entry points; **not re-implemented**).
- An optional `BrowserSessionFactory` callable for Playwright wiring.
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

    def __init__(self, settings: Settings) -> None: ...

    def load_certificate(self) -> LoadedCertificate: ...
    def health(self, *, now: datetime | None = None) -> CertificateHealth: ...
    def verify_handshake(self) -> HandshakeResult: ...

    async def authenticate(
        self,
        *,
        browser_session: BrowserSessionLike | None = None,
        target_url: str | None = None,
    ) -> AeatSession: ...

    async def reauthenticate(
        self,
        session: AeatSession,
    ) -> AeatSession: ...

    async def verify_login(
        self,
        session: AeatSession,
        *,
        target_url: str | None = None,
    ) -> AeatLoginAssertion: ...

    def extract_nif_from_subject(
        self,
        cert: LoadedCertificate,
    ) -> str: ...

    async def close(self) -> None: ...
```

`reauthenticate(session)` is the recovery path when a downstream
call sees a 401 / 403 or `verify_login()` returns
`certificate_recognised=False`. Semantics:

- Drops the current Playwright context and `storage_state`.
- Re-runs `authenticate()` with the same cert and target URL.
- Returns a new `AeatSession` with a fresh `authenticated_at` +
  `idle_deadline`.
- Enforces a **hard cap of one retry per downstream call-site** to
  avoid burning AEAT anti-bot signals. Callers that observe a
  failed `verify_login()` after `reauthenticate()` must raise
  `AeatSessionExpiredError` upwards, not loop.
- Raises `CertificateExpiredError` directly if the cert itself has
  expired since the original `authenticate()`; the old session is
  discarded regardless.

Behavioural contract:

- `load_certificate()` / `health()` / `verify_handshake()` are thin
  forwarders to the existing module-level functions, parameterised by
  `self.settings`. They let callers use the authenticator without
  Playwright at all (e.g. the doctor row, CLI cert checks).
- `authenticate()` is the **only** entry point that drives
  Playwright. It loads the cert (raising on expiry / missing env
  var), builds the client-cert kwarg via the Playwright backend,
  constructs a `BrowserContext`, and stamps the
  `_aeat_certificate_thumbprint` marker that
  `preload_into_browser_context()` validates.
- `verify_login()` navigates the authenticated context to
  `target_url` (defaulting to
  `Settings.aeat_certificate_verify_url`) and parses the
  surfaced NIF from the cert subject + the HTTP response code.
  Returns an `AeatLoginAssertion`.
- `close()` releases the context + browser cleanly.

### D2 — `AeatSession` pydantic record

New record in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`:

```python
class AeatSession(BaseModel):
    model_config = ConfigDict(
        strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True,
    )

    certificate_thumbprint: str
    certificate_subject: str
    certificate_nif: str
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_path: Path | None
    handshake: HandshakeResult

    def is_stale(self, now: datetime | None = None) -> bool: ...
```

Fields:

- `certificate_thumbprint` — SHA-256 hex of the cert's DER encoding
  (same value used by the browser context marker). Ties the session
  to a specific bundle.
- `certificate_subject` — RFC-4514 subject DN.
- `certificate_nif` — NIF extracted from the cert subject by
  `extract_nif_from_subject()`. See D5 for the parser.
- `authenticated_at` — UTC timestamp of `authenticate()` return.
- `idle_deadline` — timezone-aware UTC timestamp beyond which the
  session MUST be re-authenticated before further use. Derived as
  `authenticated_at + AEAT_SESSION_IDLE_TTL`. The TTL is a
  module-level constant in `aeat.adapters.outbound.aeat.auth._authenticator`
  (`AEAT_SESSION_IDLE_TTL = timedelta(minutes=18)`); **not a new env
  var** (per the anti-fragmentation mandate — AEAT's observed idle
  window is ~20 minutes and 18 minutes gives a safety margin, but
  the value is a code-level constant, not an operator knob).
- `storage_state_path` — Playwright `storage_state` JSON location
  (or None if the caller chose not to persist).
- `handshake` — embedded `HandshakeResult` proving the TLS leg
  succeeded. Kept as a field so callers can inspect `elapsed_ms`
  etc. without re-running the probe.

`is_stale(now)` returns `now > self.idle_deadline`; default `now`
is `datetime.now(UTC)`. The session carries **no secret material**.
It is safe to log, and its `model_dump()` / `model_dump_json()`
surfaces are safe for the audit log and doctor row.

#### Cert-expires-mid-session semantics

If the underlying PKCS#12 cert expires while a session is open, the
session record is **not mutated**. Any subsequent call through the
authenticator (`authenticate()`, `reauthenticate()`, `verify_login()`)
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
    handshake_success: bool
    certificate_recognised: bool
    parsed_nif: str | None
    parsed_subject: str | None
    status_code: int
    elapsed_ms: int
    attempted_at: datetime
    error_message: str | None
```

- `handshake_success` — TLS handshake succeeded (via
  `verify_handshake()` leg).
- `certificate_recognised` — AEAT portal returned a non-challenge
  response for the cert. Determined by the Playwright navigation
  returning HTTP 2xx/3xx with the cert supplied, versus 401/403 or a
  cert-challenge page.
- `parsed_nif` / `parsed_subject` — from the cert itself, not from
  scraped AEAT HTML (HTML surface is too volatile; the cert subject
  is authoritative and immutable per bundle).
- `is_valid` — `handshake_success AND certificate_recognised AND
  parsed_nif is not None`. Predicate field name (not a verb);
  downstream code reads `if assertion.is_valid: ...`.
- When `is_valid` is False and `certificate_recognised` is False,
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

New callable in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py`, re-exported from
`aeat.adapters.outbound.aeat.auth`:

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

**Cross-cutting home rationale:** `aeat.adapters.outbound.aeat.auth._gate` lives in
`aeat.adapters.outbound.aeat.auth` rather than `aeat.adapters.outbound.aeat.export` because the gate is
cross-cutting (it serves both live-reads via
`require_live_read()` and live-writes via `require_live_write()`).
`aeat.adapters.outbound.aeat.export` imports from `aeat.adapters.outbound.aeat.auth` via the subpackage root
(`from aeat.adapters.outbound.aeat.auth import AeatAccessGate`) per the project's public-
API discipline.

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

`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:BrowserSession.create_context()`:

- The `auth_backend: object | None` parameter is renamed to
  `cert: LoadedCertificate | None` (typed, not `object`). Type is
  the real type.
- When `cert is not None`, call
  `build_client_certificates_kwarg(cert, self.settings.aeat_certificate_verify_url)`
  (a small helper moved out of `_playwright_context.py` for direct
  reuse) and merge the result into `context_kwargs` **before**
  `browser.new_context(**context_kwargs)`.
- After the context exists, set
  `setattr(context, "_aeat_certificate_thumbprint", cert.sha256_thumbprint)`
  so the `PlaywrightContextBackend.preload()` validation passes.
- Unit test asserts the thumbprint attribute is present on the
  returned context when a cert is supplied, and absent otherwise.

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

A new live test `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py`:

- Marker: `@pytest.mark.live` (the only registered marker; the
  handover prompt's `live_read` / `domain_aeat_remote` are **not**
  valid under `--strict-markers`).
- Skip semantics (matching existing live tests):
  - Skip when `AEAT_LIVE_TESTS_ENABLED != "1"`.
  - Skip when `AEAT_CERTIFICATE_PATH` / `AEAT_CERTIFICATE_PASSWORD_SECRET`
    are unset.
- Exercises:
  - `AeatAuthenticator(Settings()).health()` returns OK severity.
  - `AeatAuthenticator(...).verify_handshake()` succeeds.
  - `extract_nif_from_subject()` returns a valid NIF shape.
  - Under a real Playwright run,
    `await authenticator.authenticate()` returns an `AeatSession`,
    and `await authenticator.verify_login(session)` returns
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

All added to `aeat.core.errors`-rooted hierarchy via `aeat.adapters.outbound.aeat.auth`:

- `AeatLiveReadNotEnabledError(AeatError)` — raised by
  `AeatAccessGate.require_live_read()` when `AEAT_LIVE_TESTS_ENABLED`
  is not `"1"`.
- `AeatLoginAssertionError(CertificateError)` — raised by
  `verify_login()` when the assertion cannot be produced (network
  error, page missing before Playwright can parse it).
- `AeatSessionExpiredError(CertificateError)` — raised when an
  `AeatSession.is_stale()` check trips, or when a single
  `reauthenticate()` attempt still yields
  `certificate_recognised=False`. Downstream callers propagate the
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
- Mathematically verifiable identity assertion: cert-derived NIF +
  TLS proof + post-auth portal reachability, captured in a frozen
  pydantic record.
- Closes the `BrowserSession` regression that would have blocked
  any real Playwright-based live read with a cert.
- Adds a symmetric read-side gate mirroring the existing write
  gate, reducing boilerplate across live tests and future CLI
  commands.
- Centralised env snapshot ends the audit-log / engine drift risk.

### Negative / accepted

- `BrowserSession.create_context(auth_backend=...)` is now
  `BrowserSession.create_context(cert=...)`. The old param was
  unused (stub), and no production call-site passes it; the change
  is API-clean. Callers that were ignoring the stub keep working.
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
  everything lands inside `aeat.adapters.outbound.aeat.auth`).
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
2. If the assertion's `certificate_recognised` is False, check
   cert registration at FNMT / AEAT. The TLS handshake can pass
   while AEAT still rejects the cert for a specific taxpayer
   profile.
3. If `parsed_nif` does not match the expected taxpayer NIF, the
   operator has the wrong cert configured. Re-check
   `AEAT_CERTIFICATE_PATH`.
