---
tags:
  - "#plan"
  - "#aeat-access-gate"
date: 2026-04-17
modified: '2026-04-17'
title: "Implementation Plan: Live AEAT Access Blocker & Verification Gate (#167)"
related:
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-aeat-access-gate-research]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-16-submission-safety-sweep-adr]]"
---

# Implementation Plan: Live AEAT Access Blocker & Verification Gate (#167)

## Preamble

Execution follows the phases below. Each phase is committable in
isolation with `just lint && just typecheck && just test` green.
Commit messages follow the conventional-commits rule (type(scope):
subject) per `CLAUDE.md`. All new public surface goes through
`aeat.adapters.outbound.aeat.auth.__init__` re-exports.

## Phase 1 — Error surface additions

- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`.
- **Content**:
  - Add `AeatLiveReadNotEnabledError(AeatError)` to the errors
    region of `certificate.py`.
  - Add `AeatSessionExpiredError(CertificateError)`.
  - Add `AeatLoginAssertionError(CertificateError)`.
  - Add `CertificateNifParseError(CertificateError)`.
  - Re-export from `aeat.adapters.outbound.aeat.auth.__init__.__all__`.
- **Tests** (`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py`): one assertion that
  every new error class is `issubclass(AeatError)` and inherits from
  the documented parent.
- **Commit**: `feat(auth): error surface for access gate (#167)`.

## Phase 2 — NIF extractor + unit tests

- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` (add
  `extract_nif_from_subject(cert) -> str`),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py`.
- **Content**:
  - Regexes for `IDCES-` prefix, DNI shape, NIE shape.
  - Function walks the `subject` RFC-4514 string and searches for a
    `serialNumber=` segment; falls back to scanning the CN if no
    serialNumber attribute is present.
  - Rejects CIF (legal-entity) with `CertificateNifParseError`.
- **Tests** (all `@pytest.mark.unit`):
  - Bare DNI in `serialNumber`.
  - `IDCES-`-prefixed DNI.
  - NIE (`X`, `Y`, `Z` prefixes).
  - CN-only fallback.
  - Empty subject → `CertificateNifParseError`.
  - CIF format (e.g. `A12345678`) → `CertificateNifParseError`.
  - Self-signed cert with an explicit `x509.NameAttribute(NameOID.SERIAL_NUMBER, ...)`
    at runtime (reuse the existing cert-generation helper).
- **Commit**: `feat(auth): extract NIF from FNMT cert subject (#167)`.

## Phase 3 — `AeatGateEnvSnapshot` + `AeatAccessGate`

- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py` (NEW),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_gate.py` (NEW — colocated Rust-style),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` (re-export).
- **Content**:
  - `AeatGateEnvSnapshot(BaseModel)`: strict, frozen,
    `extra="forbid"`; fields
    `aeat_live_tests_enabled: str`,
    `aeat_live_submit_enabled: str`,
    `pytest_current_test: str`.
  - `AeatAccessGate` dataclass (frozen, slots); constructor takes
    `settings: Settings`.
    - `require_live_read() -> None` — raises
      `AeatLiveReadNotEnabledError` when
      `os.environ.get("AEAT_LIVE_TESTS_ENABLED") != "1"`.
    - `require_live_write() -> None` — raises
      `AeatLiveSubmitNotEnabledError` when
      `self.settings.aeat_live_submit_enabled` is False;
      `AeatPytestLiveWriteRefusedError` when
      `"PYTEST_CURRENT_TEST" in os.environ`.
    - `snapshot_env() -> AeatGateEnvSnapshot` — builds the record
      from `os.environ`.
- **Tests** (all `@pytest.mark.unit`):
  - `require_live_read` raises / passes based on env var.
  - `require_live_write` raises on each failure mode.
  - `snapshot_env` returns the expected strings.
  - Env isolation via `monkeypatch.setenv` / `delenv`.
- **Commit**: `feat(auth): AeatAccessGate + env snapshot (#167)`.

## Phase 4 — `AeatSession` + `AeatLoginAssertion` records

- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` (NEW — records only
  in this phase; class lands in Phase 6),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py` (NEW),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` (re-export records).
- **Surface-stability boundary**: until Phase 6 lands,
  `aeat.adapters.outbound.aeat.auth.__all__` exposes the `AeatSession` /
  `AeatLoginAssertion` records **without** an `AeatAuthenticator`
  lifecycle owner. Downstream consumers (#168–#171 roadmap) MUST
  NOT pin imports against `aeat.adapters.outbound.aeat.auth` until the end-of-Phase-6
  commit SHA (the facade class); Phases 4–6 are reviewable
  together as a single unit rather than incrementally.
- **Content**:
  - `AEAT_SESSION_IDLE_TTL: Final[timedelta] = timedelta(minutes=18)`.
  - `AeatSession(BaseModel)` — fields per ADR D2. Method
    `is_stale(now=None) -> bool`.
  - `AeatLoginAssertion(BaseModel)` — fields per ADR D3 (with
    `is_valid` rather than `success`).
- **Tests**:
  - Construct `AeatSession` with explicit `idle_deadline`;
    `is_stale(now)` True/False based on `now`.
  - Round-trip `model_dump_json()` carries no secret; schema
    `extra="forbid"` rejects unknown fields.
  - `AeatLoginAssertion.is_valid` reflects composition of the three
    boolean gates.
- **Commit**: `feat(auth): AeatSession + AeatLoginAssertion records (#167)`.

## Phase 5 — Fix BrowserSession cert wiring (G2 regression)

- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py`,
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py` (no
  change to behaviour; confirm `_MARKER_ATTR` export for tests).
- **Content**:
  - Rename `auth_backend: object | None` to
    `cert: LoadedCertificate | None` (typed).
  - In `create_context()`, when `cert is not None`:
    - Call `build_client_certificates_kwarg(cert, origin=...)` with
      the origin derived from `self.settings.aeat_certificate_verify_url`.
    - Merge the resulting list into `context_kwargs["client_certificates"]`
      before the `new_context(**context_kwargs)` call.
    - After context creation, set
      `context._aeat_certificate_thumbprint = cert.sha256_thumbprint`
      via `setattr(context, _MARKER_ATTR, cert.sha256_thumbprint)`.
  - Re-export `_MARKER_ATTR` via a named constant so tests and the
    backend share it.
- **Tests** (unit):
  - With `cert=None`, the returned context lacks the marker
    attribute.
  - With `cert` supplied, the marker equals
    `cert.sha256_thumbprint`.
  - `build_client_certificates_kwarg` is invoked with the expected
    origin (capture via a fake Playwright stub; see §Testing
    strategy).
- **Commit**: `fix(browser): propagate cert into Playwright context (#167)`.

## Phase 6 — `AeatAuthenticator` class

- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` (extend),
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py`.
- **Content**:
  - Class per ADR D1, including `__aenter__` / `__aexit__` so it
    can be used as `async with AeatAuthenticator(settings) as a: ...`.
  - Methods:
    - `load_certificate()`, `health()`, `verify_handshake()` — thin
      forwarders using `self.settings`.
    - `extract_nif_from_subject(cert)` — forwards to the module
      function.
    - `authenticate(browser_session=None, target_url=None)` —
      when `browser_session` is None, authenticator creates its own
      via the `BrowserSessionFactory` injected at construction;
      when provided, uses it (preserves existing session factories
      elsewhere). Returns `AeatSession` with
      `idle_deadline = authenticated_at + AEAT_SESSION_IDLE_TTL`.
    - `verify_login(session, target_url=None)` — navigates
      the authenticated context to `target_url`; returns
      `AeatLoginAssertion`. Catches `PlaywrightTimeoutError`,
      generic network errors, and converts them to a record with
      `is_valid=False` + descriptive `error_message`.
      Raises `AeatLoginAssertionError` only for structural
      failures (no context, mismatched thumbprint).
    - `reauthenticate(session)` — drops current context, re-runs
      `authenticate()`, returns the new session. Single-shot: the
      method itself does not loop; callers cap retries.
    - `close()` — idempotent cleanup.
  - Async lock around `authenticate()` / `reauthenticate()` /
    `close()` to guard concurrent calls.
- **Tests**:
  - Unit tests use a fake `BrowserSessionFactory` returning a
    stand-in context with the marker already set. Zero Playwright
    dependency in the unit path.
  - Exercise `is_stale` boundaries, `reauthenticate()` single-shot
    semantics, `AeatSessionExpiredError` on repeated failure.
- **Commit**: `feat(auth): AeatAuthenticator facade + session lifecycle (#167)`.

## Phase 7 — Engine integration (env-snapshot consolidation)

- **Files**: `src/aeat/adapters/outbound/aeat/export/_engine.py`,
  `src/aeat/adapters/outbound/aeat/export/_audit.py`,
  `src/aeat/adapters/outbound/aeat/export/test_engine.py`.
- **Content**:
  - In `_submit_with_transport()`:
    - **Lines 207-212 MUST remain byte-identical.** Those are the
      three inline gate checks (`live_transport_supported`,
      `aeat_live_submit_enabled`, `PYTEST_CURRENT_TEST`). The
      executor must not touch them.
    - **Lines 213-217 only** — the ad-hoc `audit_env_state = {...}`
      dict literal — is replaced with:
      ```python
      gate = AeatAccessGate(self.settings)
      audit_env_state = gate.snapshot_env().model_dump(mode="json")
      ```
      The gate construction is inline; no `self.gate`, no kwarg
      on `SubmissionEngine.__init__`.
  - `_audit.py`'s own re-read in `build_live_submit_audit_record`
    is **not removed** — it remains as R6 last-mile defence for
    callers that forget to thread `env_state` through.
  - Add a regression test asserting the dict keys in
    `audit_env_state` still match the audit JSONL schema (no
    breaking change to the log format).
- **Tests** (unit):
  - Engine path with `dry_run=False` constructs the gate inline
    and hands the snapshot into the audit record.
  - `_audit.append_record(env_state=None)` still works and
    produces the three expected keys (fallback).
- **Commit**: `refactor(submission): source audit env snapshot from AeatAccessGate (#167)`.

## Phase 8 — `env/.env.example` documentation block

- **Files**: `env/.env.example`.
- **Content**: the comment block from ADR D8 inserted near the
  other AEAT cert env docs.
- **Tests**: `tests/test_config.py` alignment scanner still green
  (no new keys; only a comment).
- **Commit**: `docs(env): document R3 omission of AEAT_LIVE_SUBMIT_ENABLED (#167)`.

## Phase 9 — Live authenticator test

- **Files**: `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py` (NEW).
- **Content**:
  - Single `@pytest.mark.live` module.
  - Skip when `AEAT_LIVE_TESTS_ENABLED != "1"` OR
    `AEAT_CERTIFICATE_PATH` unset OR
    `AEAT_CERTIFICATE_PASSWORD_SECRET` unset.
  - Assertions:
    - `AeatAuthenticator(Settings()).health().severity in {OK, WARN}`.
    - `verify_handshake()` returns `success=True`, `200 <= status_code < 500`.
    - `extract_nif_from_subject(load_certificate(...))` returns a
      valid DNI or NIE shape.
    - `async with AeatAuthenticator(Settings()) as auth:`
      - `session = await auth.authenticate()` — succeeds.
      - `assertion = await auth.verify_login(session)` — returns
        record with `is_valid=True`, `certificate_recognised=True`,
        `parsed_nif == session.certificate_nif`.
      - `session.is_stale()` is False immediately after auth.
  - Zero mocks / patches / fakes (R5 + `tests/conftest.py`
    enforcement).
- **Commit**: `test(auth): live AeatAuthenticator verification (#167)`.

## Phase 10 — Doctor row (mandatory)

- **Files**: `src/aeat/entrypoints/cli/doctor.py`.
- **Content**: a single "Live access gate" row driven by
  `AeatAccessGate(settings).snapshot_env()` — OK when
  `AEAT_LIVE_TESTS_ENABLED=="1"`, WARN when absent, MISSING if
  the read-gate would refuse. The row surfaces the three env var
  states (no secret values). This row is promised by the ADR's
  §Operator-runbook and must ship in this PR.
- **Tests** (`src/aeat/entrypoints/cli/test_doctor.py`): new case asserting
  the row renders the expected state per env configuration.
- **Commit**: `feat(cli): doctor row for live access gate env (#167)`.

## Phase 11 — Docs + vaultspec execution records

- **Files**: `.vault/exec/2026-04-17-aeat-access-gate/*.md`
  (one step record per phase above), plus
  `.vault/exec/2026-04-17-aeat-access-gate/2026-04-17-aeat-access-gate-summary.md`.
- **Content**: frontmatter tags `["#exec", "#aeat-access-gate"]`,
  wiki-link back to this plan + the ADR.
- **Commit**: `docs(aeat-access-gate): exec records + phase summary (#167)`.

## Phase 12 — Mandatory code review

- **Files**: `.vault/exec/2026-04-17-aeat-access-gate/2026-04-17-aeat-access-gate-code-review.md`.
- **Content**: delegate to the `vaultspec-code-reviewer` persona
  with the full diff context. Review all added/changed files for:
  - R1–R6 compliance (no write-gate weakening).
  - pydantic v2 strict/frozen discipline on every new record.
  - Public API discipline (imports from subpackage root only).
  - Type-checker clean, ruff clean, tests clean.
- **Commit**: `docs(aeat-access-gate): mandatory code review record (#167)`.

## Testing strategy

- **Unit tests** `@pytest.mark.unit`, colocated per module.
- **No Playwright import path under pytest unit runs.** The
  authenticator accepts an injectable `BrowserSessionFactory` for
  unit tests; the factory returns a stand-in context that honours
  the `_aeat_certificate_thumbprint` marker contract.
- **One live test** `@pytest.mark.live` gated on env vars per
  `pyproject.toml` marker catalogue (`unit`, `live`, `flaky`
  only).
- **Coverage floor** 60% via `just test-cov` (unchanged).
- Pre-commit on every commit: `just lint && just typecheck &&
  just test && just hooks`.

## Architectural invariants

- **No new subpackage.** Everything lives under `aeat.adapters.outbound.aeat.auth`.
- **No new env var.** Session TTL is a hard-coded constant.
- **`SubmissionEngine` interface unchanged.** No `gate=` kwarg,
  no `self.gate`, no injection seam.
- **Audit JSONL schema unchanged.** Only the data source for the
  env-state field shifts inside the engine.
- **Write gate semantics preserved.** The nine-point gate in
  `_submit_with_transport()` is byte-identical for the inline
  checks.

## Plan self-review (no human in the loop)

### Risks considered

1. **AEAT recognises the cert at TLS but not at session** — handled
   by splitting `handshake_success` from `certificate_recognised`
   on `AeatLoginAssertion`. Downstream code reads
   `is_valid` for the composite predicate.
2. **Playwright context creation fails intermittently (bot
   detection)** — the existing `EvasionStrategy` applies before
   cert wiring; order of operations preserved in Phase 5.
3. **NIF parser misses an FNMT subject variant** — six unit cases
   cover the known shapes; CIF and unknown formats raise
   `CertificateNifParseError` rather than silently accept.
4. **Audit-log field drift** — the engine snapshot builder and the
   `_audit.py` fallback both emit the same three keys. A unit test
   asserts their JSON output is equal under a frozen env.
5. **Concurrency** — `asyncio.Lock` around `authenticate()` /
   `reauthenticate()` / `close()`. Idempotent `close()`.
6. **Test-time gate substitution** — no kwarg seam; gate is
   constructed inline from `Settings`; tests cannot substitute it.
