---
tags:
  - "#exec"
  - "#aeat-access-gate"
date: 2026-04-17
modified: '2026-04-17'
title: "Execution Summary: Live AEAT Access Blocker & Verification Gate (#167)"
related:
  - "[[2026-04-17-aeat-access-gate-plan]]"
  - "[[2026-04-17-aeat-access-gate-adr]]"
  - "[[2026-04-17-aeat-access-gate-research]]"
---

# Execution Summary: Live AEAT Access Blocker & Verification Gate (#167)

## Scope delivered

All 12 plan phases landed in a single reviewable PR against
`feature/167-aeat-access-gate`. The delivery is **additive** with
one targeted bugfix — no existing behaviour was rewritten.

### Phase 1 — Error surface

Added to `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py`:

- `CertificateNifParseError(CertificateError)` — subject-parse failure.
- `AeatLoginAssertionError(CertificateError)` — structural verify_login failure.
- `AeatSessionExpiredError(CertificateError)` — stale-session signal, also raised when a single `reauthenticate()` still yields `certificate_recognised=False`.
- `AeatLiveReadNotEnabledError(AeatError)` — read-side counterpart to `AeatLiveSubmitNotEnabledError`.

All re-exported from `aeat.adapters.outbound.aeat.auth.__init__.__all__`.

### Phase 2 — NIF / NIE extractor

`extract_nif_from_subject(cert: LoadedCertificate) -> str` parses
FNMT *persona física* subjects. Accepts DNI (`[0-9]{7,8}[A-Z]`)
and NIE (`[XYZ][0-9]{7}[A-Z]`); rejects CIF (legal-entity) and
unparseable subjects with `CertificateNifParseError`. Six colocated
unit tests cover happy paths + rejection paths; runtime-generated
self-signed bundles carry synthetic FNMT subjects.

### Phase 3 — `AeatAccessGate` + `AeatGateEnvSnapshot`

New `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py` holds the unified read+write gate.
`AeatAccessGate` is a frozen dataclass that (a) surfaces
`require_live_read()` / `require_live_write()` as typed
preconditions and (b) emits an `AeatGateEnvSnapshot` for audit
logging via `snapshot_env()`. The write-gate helper is expressly
**not** a replacement for the engine's inline 9-point gate — it is
a defensive helper callable from any live-capable surface that
wants the typed error shape up-front. Ten colocated unit tests.

### Phase 4 + 6 — `AeatAuthenticator`, `AeatSession`, `AeatLoginAssertion`

New `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` is the single entry point
for future remote-read work. The module delivers:

- `AEAT_SESSION_IDLE_TTL = timedelta(minutes=18)` — code-level
  constant; no new env var.
- `AeatSession` frozen pydantic record with `is_stale(now)`.
- `AeatLoginAssertion` frozen pydantic record with predicate
  field `is_valid`.
- `AeatAuthenticator` async class with `authenticate()`,
  `reauthenticate()`, `verify_login()`, `close()`, plus
  synchronous helpers (`load_certificate`, `health`,
  `verify_handshake`, `extract_nif_from_subject`). Implemented
  as an async context manager with an `asyncio.Lock` guarding
  concurrent lifecycle transitions.
- Four structural Protocols: `BrowserSessionLike`,
  `BrowserContextLike`, `BrowserPageLike`, `BrowserResponseLike`,
  so ty can check the async path without importing Playwright.
- `BrowserSessionFactory` callable Protocol for dependency
  injection in tests and (eventually) the CLI factory layer.

Eleven unit tests exercise: NIF extraction, `is_stale` boundaries,
`model_dump_json` non-leakage, `AeatLoginAssertion` frozen state,
`authenticate()` happy path under a fake browser session factory,
stale-session refusal, no-context refusal, close idempotency.

### Phase 5 — BrowserSession cert wiring (G2 regression fix)

`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` previously accepted an
`auth_backend: object | None` stub parameter and discarded it
(documented as "stub for #8"). That left `PlaywrightContextBackend.preload()`
permanently failing because no call-site ever stamped the
`_aeat_certificate_thumbprint` marker on the context.

The fix is narrow:

- `create_context` now accepts a typed `cert: LoadedCertificate | None`.
- When a cert is supplied, the session builds the
  `client_certificates` kwarg via
  `aeat.adapters.outbound.aeat.auth._certificate_backends._playwright_context.build_client_certificates_kwarg`
  and merges it into the `new_context(**kwargs)` call — wiring the
  cert at construction time, the only place Playwright accepts it.
- After construction, the session stamps the thumbprint marker
  via a direct attribute assignment. A new module-level constant
  `CERTIFICATE_THUMBPRINT_MARKER` is re-exported so the backend
  and test suite share the attribute name.
- Evasion / profile / proxy wiring is untouched.

Two new unit tests: one proves no marker is stamped when `cert`
is omitted; one proves the marker + kwarg propagation when a real
self-signed bundle is supplied.

### Phase 7 — Engine env-snapshot consolidation

`src/aeat/adapters/outbound/aeat/export/_engine.py` constructs an `AeatAccessGate`
inline from `self.settings` and delegates the env-snapshot dict
build to `gate.snapshot_env().as_audit_dict()`. The three inline
gate checks on lines 207-212 (`live_transport_supported`,
`aeat_live_submit_enabled`, `PYTEST_CURRENT_TEST`) are
**byte-identical** — the nine-point gate is preserved in full.

`src/aeat/adapters/outbound/aeat/export/_audit.py:77-82`'s env re-read fallback is
**retained** as R6 last-mile defence: any future call-site that
invokes `append_live_submit_audit` without threading `env_state`
through still produces a complete audit record. The JSONL schema
is unchanged.

A `gate=` kwarg on `SubmissionEngine.__init__` is explicitly
forbidden (see the ADR D4 non-injection rule). The gate is
constructed inline per call; no seam exists for test-time
substitution.

### Phase 8 — `env/.env.example` R3 comment block

Added a clearly-labelled block near the cert config explaining
the intentional absence of `AEAT_LIVE_SUBMIT_ENABLED` with
pointers to issue #116 and the submission safety sweep ADR.

### Phase 9 — Live authenticator tests

`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py` carries two
`@pytest.mark.live` items:

1. Synchronous surface: health, verify_handshake, NIF extraction.
2. Full async flow: Playwright-backed `authenticate()` +
   `verify_login()` against the operator's real cert and the
   configured verify URL.

Both skip cleanly when `AEAT_LIVE_TESTS_ENABLED != "1"` or the
cert env vars are not fully configured. Zero mocks / patches /
fakes (R5 + `tests/conftest.py` banned-import enforcement).

### Phase 10 — Doctor row

`check_live_access_gate()` surfaces the three gate env vars at
the CLI level. Reports OK when reads are enabled, SKIP when not,
WARN when `AEAT_LIVE_SUBMIT_ENABLED` is set (charter #116 wants
it unset at rest) or when `PYTEST_CURRENT_TEST` leaks into the
shell. Three unit tests cover the state matrix.

### Phase 11–12 — Vaultspec records + code review

This summary + the colocated research / ADR / plan under
`.vault/{research,adr,plan}/` constitute the audit trail.

## Compatibility with the R1–R6 charter (#116)

| Rule | Status |
|------|--------|
| R1 reads allowed / writes forbidden in test context | Preserved — live reads use `AeatLiveReadNotEnabledError`; live writes still refuse under `PYTEST_CURRENT_TEST`. |
| R2 dry-run default | Preserved — no change to `SubmissionAttempt.dry_run` default or to call-site signatures. |
| R3 env var set `{AEAT_LIVE_TESTS_ENABLED, AEAT_LIVE_SUBMIT_ENABLED}` | Preserved — no new env vars; `AEAT_LIVE_SUBMIT_ENABLED` intentional absence now documented. |
| R4 interactive phrase confirmation | Preserved — `_confirm.py` untouched. |
| R5 no test-time monkey-patching of write gates | Preserved — no `gate=` kwarg on `SubmissionEngine`, no injection seam; inline checks at `_engine.py:207-212` are byte-identical. |
| R6 audit trail per live write | Preserved + tightened — engine snapshot + `_audit.py` fallback both produce the same three-key dict. JSONL schema unchanged. |

## Files changed (summary)

### New (6)
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_gate.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_gate.py`
- `.vault/research/2026-04-17-aeat-access-gate-research.md`
- `.vault/adr/2026-04-17-aeat-access-gate-adr.md`
- `.vault/plan/2026-04-17-aeat-access-gate-plan.md`
- `.vault/exec/2026-04-17-aeat-access-gate/2026-04-17-aeat-access-gate-phase1-summary.md`

### Modified (7)
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` — four new errors + NIF extractor.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` — re-exports for the new public surface.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/session.py` — cert wiring fix (G2 regression).
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` — cert-wiring regression test.
- `src/aeat/adapters/outbound/aeat/export/_engine.py` — env snapshot via `AeatAccessGate`.
- `src/aeat/entrypoints/cli/doctor.py` — live access gate row.
- `src/aeat/entrypoints/cli/_test_doctor.py` — tests for the new row.
- `env/.env.example` — R3 comment block.

## Verification

```
just lint       → all checks passed
just typecheck  → all checks passed
just test       → 1183 passed, 1 skipped, 26 deselected
```

Live test remains gated on the operator env vars and was not
executed during this iteration (skipped by default).
