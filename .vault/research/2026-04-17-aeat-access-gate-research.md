---
tags:
  - "#research"
  - "#aeat-access-gate"
date: 2026-04-17
modified: '2026-04-17'
title: "Research: Live AEAT Access Blocker & Verification Gate (#167)"
related:
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-playwright-anti-bot-adr]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
---

# Research: Live AEAT Access Blocker & Verification Gate (#167)

## 1. Mandate

Issue #167 positions itself as the **absolute milestone gate** for the
`domain:aeat-remote` track: no bi-directional AEAT feature ships until
the project has a robust, mathematically verified live certificate auth
path and a unified access / write gate. The user has further mandated
that any architectural regression in the existing auth / write layers
is in scope for remediation, and that correctly gating write access —
at CLI, API, and code-path level — is non-negotiable because every
AEAT write is a legally binding tax act.

Companion issues already shipped:

- #8 — PKCS#12 certificate loader + backends (`aeat.adapters.outbound.aeat.auth.certificate`).
- #94 — Pre-expiry health gate (`CertificateHealth`, doctor row,
  submit flag).
- #116 — Live-AEAT-write safety charter R1–R6 (permanent pointer).
- #117 — `AEAT_LIVE_SUBMIT_ENABLED` env var + dry-run-by-default +
  human confirmation guard.
- #118 — Static code audit of live-AEAT-write call-sites.

This research grounds a decision on what #167 adds on top of that
stack.

## 2. Audit method

Audit scope: every module under `src/aeat/` that could either read or
write against AEAT Sede Electrónica. Each finding below carries a
`file_path:line_number` pointer for traceability. The audit was run on
the feature/167 branch at head `185c21e` (test-infra pytest lockdown).

## 3. What already exists (functional inventory)

### 3.1 Certificate auth surface (`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/`)

- Public module `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` (682 LOC) — all pydantic v2
  boundary records (`CertificateBundle`, `LoadedCertificate`,
  `HandshakeResult`, `CertificateHealth`), loader, health evaluator,
  backend dispatch.
- Private backends in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/`:
  - `_playwright_context.py` — primary; supplies PKCS#12 to
    `browser.new_context(client_certificates=[...])` via
    `build_client_certificates_kwarg()`. `preload()` validates the
    browser context carries the `_aeat_certificate_thumbprint` marker.
  - `_httpx_fallback.py` — verify-only mTLS probe. Extracts PEM,
    writes 0600 temp files, `try/finally` cleanup. Used by
    `verify_handshake()`.
  - `_user_data_dir.py` + `_mtls_proxy.py` — stubbed with
    `NotImplementedError` and docstring rationale.
- Secrets discipline: `SecretStr` + `PrivateAttr` for pkcs12 bytes,
  passphrase, and parsed key handle. `__repr__` override blocks
  accidental leaks.
- Error hierarchy: `CertificateError → {LoadError, PasswordError,
  ExpiredError, HandshakeError, PreExpiryError}`, all inheriting from
  `aeat.core.errors.AeatError`.

### 3.2 Existing gates and their call-sites

The live-write gate is a **nine-point sequence** inside
`SubmissionEngine._submit_with_transport()`
(`src/aeat/adapters/outbound/aeat/export/_engine.py:181-315`) plus the CLI wrapper.
Gate map:

| # | Gate                                   | Source                                                              | Bypass difficulty |
|---|----------------------------------------|---------------------------------------------------------------------|-------------------|
| 1 | Draft status `READY_TO_SUBMIT`         | `_preflight.py:77-80`                                               | Must set status   |
| 2 | No ERROR-severity findings             | `_preflight.py:82-91`                                               | Must clear errors |
| 3 | Deadline window open                   | `_preflight.py:93-103`                                              | Calendar-bound    |
| 4 | Certificate loads cleanly + not EXPIRED| `_preflight.py:105-114`, `cli/submission/submit.py:113`             | Real cert required|
| 5 | CLI flag `--i-understand-this-is-real` | `cli/submission/submit.py:105-107`                                  | CLI code change   |
| 6 | Transport supported by engine          | `_engine.py:203-206`                                                | Constructor arg   |
| 7 | `AEAT_LIVE_SUBMIT_ENABLED=true`        | `_engine.py:207-208` via `Settings.aeat_live_submit_enabled`        | Operator env      |
| 8 | `PYTEST_CURRENT_TEST` **absent**       | `_engine.py:209-212`                                                | Physically impossible under pytest |
| 9 | Interactive phrase confirmation        | `_confirm.py:29-58` (exact phrase `SUBMIT {modelo} {period} {nif} {total} {checksum}`) | stdin hijack only |

Each successful live-write is additionally logged to an append-only
JSONL at `.aeat/live-submit-audit.log` (`src/aeat/adapters/outbound/aeat/export/_audit.py`)
with timestamp, draft checksum, submission URL, response status,
confirmation phrase, env state, PID. After append the file is chmod
0400 to prevent in-process rewrite.

### 3.3 Test markers + live reads

`pyproject.toml [tool.pytest.ini_options]` registers **only three**
markers: `unit`, `live`, `flaky`. The addopts line
`-m 'not live' --strict-markers` guarantees `@pytest.mark.live` is
skipped by default and that an invented marker (e.g.
`@pytest.mark.live_read` or `@pytest.mark.domain_aeat_remote` that the
handover prompt loosely referenced) fails collection. **We must stay
inside the `unit` / `live` catalogue for this feature.**

`tests/conftest.py` additionally bans `unittest`, `unittest.mock`,
`mock`, `pytest_mock`, `pytest_httpx`, `time_machine`, `freezegun`,
`vcr` from any file that contains a `@pytest.mark.live` item. This is
a belt-and-braces extension of the R5 rule (no test-time monkey-patching
of write-capable call-sites).

Live-read tests that exist today (all gated on
`AEAT_LIVE_TESTS_ENABLED=1`):

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py` — verify_handshake smoke.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py` — bot-detection probe.
- `src/aeat/domain/casillas/test_live_cli.py` — casilla catalogue fetch.
- `src/aeat/inbox/test_live_inbox.py` — notifications fetch + ack.
- `src/aeat/application/sync/test_live_sync.py` — status-reader sync.
- `src/aeat/domain/justificante/test_verify_live.py` — PDF fetch.
- `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` — dry-run end-to-end
  (never calls submit with `dry_run=False`).

### 3.4 Browser session layer

`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:BrowserSession.create_context()` accepts
an `auth_backend: object | None = None` parameter (line 50). The body
(line 113) is a no-op with an inline `# stub for #8` comment —
**the certificate is never propagated into the Playwright context**.

## 4. Gaps (what #167 must fix / add)

### G1 — No unified `AeatAuthenticator` facade

Certificate lifecycle is scattered:

- Doctor row (`src/aeat/entrypoints/cli/doctor.py:620-643`) reads the env var and
  calls `certificate_health()` directly.
- Submit CLI (`src/aeat/entrypoints/cli/submission/submit.py:45-78,113`) repeats
  the same pattern.
- Preflight (`src/aeat/adapters/outbound/aeat/export/_preflight.py:105-114`) calls
  `load_certificate()` a third time, catching its own error shape.
- Browser session (`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py:113`) pretends to
  accept a cert but discards it.

Future remote-read modules (#168 filing history, #169 missing filings,
#170 AEAT messages, #171 VAT balance tracking) will all need the same
authenticated Playwright context. Without a single entry point they
will each re-invent the wiring, which is exactly the fragmentation the
user flagged.

### G2 — Browser session regression: thumbprint marker never set

`PlaywrightContextBackend.preload()`
(`_playwright_context.py:86`) asserts that the `BrowserContext`
carries a `_aeat_certificate_thumbprint` marker attribute matching the
loaded cert. Nothing in `BrowserSession.create_context()` sets that
marker. If anyone wires the backend properly (as #167 requires) the
preload() validation always fails.

### G3 — No live login assertion

`verify_handshake()` only proves the server accepts the client
certificate during the TLS handshake against `sede.agenciatributaria.gob.es/`.
That URL returns a public landing page (HTTP 200) regardless of whether
the cert is recognised as a specific taxpayer. We have no evidence
path that parses the logged-in NIF / subject from a post-auth screen
(e.g. the "Mis expedientes" portal or the `SelectorCertificado`
redirect target).

This is the **mathematical verification** #167 is asking for:
certifying that (a) the TLS handshake succeeded **and** (b) AEAT
identified the certificate holder **and** (c) the authenticated
identity matches the expected NIF.

### G4 — No `AeatSession` record

Browser cookies + localStorage are persisted to
`profile.storage_state_path` as an opaque Playwright JSON blob. We
have no pydantic record capturing: authenticated NIF, authenticated
subject CN, authentication timestamp, cert thumbprint tying the
session to a specific bundle, nor an expiry / renewal clock.

Without that record, future remote-read call-sites have no way to
declare "I require an authenticated session ≤ N minutes old for the
same NIF as the configured certificate". They will re-authenticate
on every call, burning AEAT trust signals and risking rate-limit /
anti-bot interception.

### G5 — Duplicated env snapshotting in audit log

`submission/_audit.py:77-82` re-reads `AEAT_LIVE_TESTS_ENABLED`,
`AEAT_LIVE_SUBMIT_ENABLED`, `PYTEST_CURRENT_TEST` at audit-write
time. The engine already captured the same data on line 214-216 of
`_engine.py`. Minor, but duplication is a drift source: if one
location is updated (new env var) the other goes stale silently.

### G6 — `AEAT_LIVE_SUBMIT_ENABLED` is intentionally absent from
`env/.env.example`, but this absence is undocumented — a reader of
the repo can't tell whether the var is missing on purpose (R3 rule)
or simply forgotten.

### G7 — No read-side gate abstraction

The nine-point gate above is exclusively a *write* gate. Live reads
rely solely on `AEAT_LIVE_TESTS_ENABLED=1` being set, checked
per-test inside `if os.environ[...] != "1": pytest.skip(...)`
boilerplate that is repeated in every live test. There is no central
"I need live AEAT access for a read, and here's why" object that can
be relied on by future read-call-sites (sync runner, filing history
fetcher, justificante poller).

## 5. Non-goals for this feature

- **No fundamental rewrite of the certificate loader.** The PKCS#12
  + SecretStr + PrivateAttr architecture is correct and tested; it
  does not need to move. We augment around it.
- **No new env vars beyond what the charter specifies.** R3 fixes
  the env var set at `{AEAT_LIVE_TESTS_ENABLED, AEAT_LIVE_SUBMIT_ENABLED}`
  + the existing cert family. Adding more would be noise.
- **No Cl@ve / DNIe.** Certificate is the only supported method.
- **No renewal automation.** The pre-expiry gate already handles
  the only piece of renewal the project owns.
- **No new subpackage.** A new `src/aeat/remote/` subpackage was
  loosely mentioned in the handover prompt; the user mandate is
  *against fragmentation*. `aeat.adapters.outbound.aeat.auth` is the natural home for the
  authenticator and session records; creating a sibling subpackage
  would scatter the cert family further.

## 6. What must change

The delta-work #167 owns:

1. **Introduce `AeatAuthenticator` + `AeatSession`** in `aeat.adapters.outbound.aeat.auth`
   (not a new subpackage). The authenticator owns the composition of
   `Settings`, `CertificateBundle`, `BrowserSession` (optional),
   `health(...)`; the session is a frozen pydantic record that
   proves "this process has live AEAT access right now".
2. **Fix G2**: wire `BrowserSession.create_context()` to accept a
   `LoadedCertificate` and (a) pass the cert through to
   `browser.new_context(client_certificates=[...])` via the
   backend's kwarg builder, (b) stamp the thumbprint marker on the
   resulting context so `preload_into_browser_context()` validation
   passes. This closes the single architectural regression detected.
3. **Add a live login assertion path** (`AeatLoginAssertion` pydantic
   record) that navigates an authenticated Playwright session to a
   known post-auth URL and parses the surfaced NIF / subject, then
   compares against the configured cert. One live test exercises it;
   skips cleanly when the cert / env are absent.
4. **Add a read-side gate** — `require_live_access(read: bool, write: bool)`
   helper in `aeat.adapters.outbound.aeat.auth` that consolidates the nine-point sequence
   but exposes it as a reusable precondition. The existing submission
   gate **keeps its own inline checks** (those are our defensive
   last-mile) but the helper gives future remote-read sites a single
   call-site and a unified error shape.
5. **Document** the `AEAT_LIVE_SUBMIT_ENABLED` intentional omission
   in `env/.env.example` via a comment block — a reader can now see
   the R3 rule without diving into the charter.
6. **Centralise env-snapshot** for the audit log (G5) in one helper
   consumed by both `_engine.py` and `_audit.py`.

## 7. Compatibility with the R1–R6 charter

Every item in §6 respects R1–R6 unchanged:

- **R1**: reads stay permitted, writes stay forbidden in test contexts.
  The new read-gate never weakens the write gate.
- **R2**: `dry_run=True` remains the default on every submission call.
- **R3**: env var set unchanged (`AEAT_LIVE_TESTS_ENABLED` +
  `AEAT_LIVE_SUBMIT_ENABLED`); the helper merely centralises the
  read of those values.
- **R4**: interactive phrase confirmation unchanged.
- **R5**: `PYTEST_CURRENT_TEST` refusal unchanged.
- **R6**: audit log unchanged in format; only the env-snapshot read
  is centralised.

## 8. Open questions

*None material.* The handover prompt mentioned markers
`@pytest.mark.live_read` and `@pytest.mark.domain_aeat_remote`; those
are **not** registered in `pyproject.toml` and would fail collection
under `--strict-markers`. We stay inside the existing `unit` / `live`
catalogue.

## 9. References

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` — public cert surface.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/*.py` — backends.
- `src/aeat/adapters/outbound/aeat/export/_engine.py` — 9-point write gate.
- `src/aeat/adapters/outbound/aeat/export/_preflight.py` — gates 1–4.
- `src/aeat/adapters/outbound/aeat/export/_confirm.py` — gate 9.
- `src/aeat/adapters/outbound/aeat/export/_audit.py` — R6 log.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` — factory missing cert wiring.
- `pyproject.toml` — marker catalogue and ban-list.
- `tests/conftest.py` — live-test banned imports.
- `env/.env.example` — env documentation surface.
- `.vault/adr/2026-04-12-cert-auth-adr.md`, `.vault/adr/2026-04-13-cert-pre-expiry-gate-adr.md`
- `[[live_write_safety]]` memory.
