---
tags:
  - "#plan"
  - "#cert-pre-expiry-gate"
date: 2026-04-13
modified: '2026-04-13'
title: "Certificate Pre-Expiry Health Check + Workflow Gate — Implementation Plan"
related:
  - "[[2026-04-13-cert-pre-expiry-gate-research]]"
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-12-workflow-engine-plan]]"
  - "[[2026-04-12-cert-auth-plan]]"
---

# Plan: Certificate Pre-Expiry Health Check + Workflow Gate

Issue: wgergely/aeat#94. Branch: `feature/94-cert-pre-expiry-gate`.

## Phase 1 — Model + evaluator in `aeat.adapters.outbound.aeat.auth`

1. Add `CertificateHealthSeverity(StrEnum)` to
   `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py`.
2. Add `CertificateHealth(BaseModel)` — strict, frozen, extra=forbid;
   fields per ADR section 1.
3. Add `CertificatePreExpiryError(CertificateError)`.
4. Implement `evaluate_loaded_certificate_health(loaded, *, warn_days,
   critical_days, now=None) -> CertificateHealth` (pure, no I/O).
5. Implement `health(path, *, password_env_var, warn_days,
   critical_days, now=None) -> CertificateHealth`; internally wraps
   `load_certificate` with a transient `CertificateBundle`, catching
   `CertificateExpiredError` and producing an EXPIRED severity record
   instead of raising.
6. Export new symbols from `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` + update
   `__all__` in `certificate.py`.

## Phase 2 — Settings + env example

1. Add `aeat_cert_warn_days: int = 60` and
   `aeat_cert_critical_days: int = 14` in `src/aeat/config.py` (next
   to the existing cert block).
2. Append matching entries under the `AEAT_CERTIFICATE_*` section of
   `env/.env.example`.
3. Confirm `tests/test_config.py::TestEnvExampleAlignment` still
   passes (pattern-based, picks up new fields automatically).

## Phase 3 — Unit tests for health

Add `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_health.py`, `@pytest.mark.unit`, reusing the
`_build_pkcs12_bundle` helper from `test_certificate.py` (imported via
the module's absolute path, not duplicated — but colocated tests
module can't import from a sibling test module, so copy the helper
into a new `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_test_pkcs12.py` private utility and have
**both** test files use it).

- On second thought: keep the helper colocated inside `test_health.py`
  as a local function; duplication is cheap and avoids a
  non-test private module under `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/`.

Scenarios covered:
- `OK` — not_after = now + 200 days.
- `WARN` (exact boundary) — not_after = now + 60 days.
- `WARN` (below boundary) — not_after = now + 30 days (still > 14).
- `CRITICAL` (exact boundary) — not_after = now + 14 days.
- `CRITICAL` (below) — not_after = now + 3 days.
- `EXPIRED` — not_after = now - 1 day; `health()` returns severity
  EXPIRED rather than raising.
- `evaluated_at` injection via explicit `now=` arg for
  deterministic boundary checks.
- Frozen model: mutation raises.
- `CertificatePreExpiryError` inherits from `AeatError`.

## Phase 4 — Workflow gate

1. In `src/aeat/application/workflow/_engine.py::_stage_running_preflight`, after
   the existing `self._certificate_bundle.load()` call, invoke
   `evaluate_loaded_certificate_health(loaded, warn_days=...,
   critical_days=...)` using `self._settings.aeat_cert_warn_days` and
   `self._settings.aeat_cert_critical_days`.
2. Severity mapping:
   - `EXPIRED` / `CRITICAL`: raise `_AbortError(CERT_INVALID, ...)`
     before the preflight call, with step details including
     `cert_severity`, `cert_days_until_expiry`,
     `cert_not_after`.
   - `WARN`: emit `_logger.warning("certificate nearing expiry: "
     "subject=%s days=%d", ...)` and merge the severity into the
     `cert_details` dict. Continue.
   - `OK`: unchanged.
3. Extend `test_engine.py` with: a test double certificate bundle
   that returns a `LoadedCertificate` with a `not_after` placed in
   each of the four buckets; assert the resulting
   `WorkflowAbortReason` and step details. Use Protocol-conforming
   test doubles (no mocks).

## Phase 5 — `aeat doctor` cert row

1. Add `check_certificate_health(settings)` in
   `src/aeat/entrypoints/cli/doctor.py` following the `Row` pattern already used.
2. Skip when `settings.aeat_certificate_path` is None.
3. On load failure return `State.WARN`, detail = exception class name.
4. On OK severity → `State.OK` with `Nd left` detail.
5. On WARN → `State.WARN` (not required); on CRITICAL/EXPIRED →
   `State.MISSING` (required, forces exit 1).
6. Insert the row before the service-account block.

## Phase 6 — Submission CLI gate

1. Add `--force-expiring-cert` option to `submit_cmd` in
   `src/aeat/entrypoints/cli/submission/submit.py`.
2. Before constructing the engine, compute `CertificateHealth` via
   `aeat.adapters.outbound.aeat.auth.health(path=settings.aeat_certificate_path, ...)` only
   if the cert path is configured; otherwise skip.
3. On CRITICAL/EXPIRED with `--force-expiring-cert` **not** set, print
   a red message and exit code 2.
4. On WARN print a yellow warning line; continue.
5. Update `submit.py` tests only if present; otherwise rely on a new
   focused unit test colocated under `src/aeat/entrypoints/cli/submission/test_submit.py`
   if one doesn't yet exist — guard with `@pytest.mark.unit`.

## Phase 7 — Quality gates + commit

`just lint`, `just typecheck`, `just test`, `just hooks`. Fix any root
causes; never skip. Conventional commits:

- `feat(auth): certificate pre-expiry health model + evaluator (#94)`
- `feat(workflow): cert pre-expiry gate in preflight stage (#94)`
- `feat(cli): doctor + submit cert pre-expiry gate (#94)`
- `docs(vault): cert pre-expiry gate research/adr/plan/exec (#94)`

Exec records land under
`.vault/exec/2026-04-13-cert-pre-expiry-gate/` with a phase summary.

## Self-review against CLAUDE.md + ADR

- ✅ Strict pydantic v2 frozen + extra=forbid on all new records.
- ✅ `StrEnum` for the severity catalogue.
- ✅ Errors inherit from `aeat.core.errors.AeatError` via
  `CertificateError`.
- ✅ Logging via `aeat.core.logging.get_logger(__name__)` (already imported
  in `certificate.py` and `_engine.py`).
- ✅ Google-style docstrings + type hints on every public symbol.
- ✅ Tests colocated under `src/aeat/...` with
  `@pytest.mark.unit`, real PKCS#12 generation, no mocks.
- ✅ Public API discipline: callers import from `aeat.adapters.outbound.aeat.auth` only;
  `_engine.py` imports the helper off `aeat.adapters.outbound.aeat.auth` (not
  `aeat.adapters.outbound.aeat.auth.certificate`).
- ✅ Sibling-branch territory untouched (`aeat.adapters.outbound.aeat.browser`,
  `aeat.status`, `aeat.application.filing`, `src/aeat/domain/financial/*`).
- ✅ No workflow file under `.github/workflows/`.
- ✅ `aeat_cert_warn_days` / `aeat_cert_critical_days` follow the
  existing `aeat_deadline_due_soon_days` shape in Settings.

## Review outcome

**Approved for execution — no outstanding blockers.**
