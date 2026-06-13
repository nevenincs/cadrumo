---
tags:
  - "#exec"
  - "#cert-pre-expiry-gate"
date: 2026-04-13
modified: '2026-04-13'
title: "Certificate Pre-Expiry Gate — Phase 1 Summary"
related:
  - "[[2026-04-13-cert-pre-expiry-gate-research]]"
  - "[[2026-04-13-cert-pre-expiry-gate-adr]]"
  - "[[2026-04-13-cert-pre-expiry-gate-plan]]"
---

# Phase 1 Summary — Certificate Pre-Expiry Gate (#94)

Implements wgergely/aeat#94 on branch `feature/94-cert-pre-expiry-gate`.

## Shipped artefacts

- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py`
  - `CertificateHealthSeverity(StrEnum)` — OK / WARN / CRITICAL / EXPIRED.
  - `CertificateHealth(BaseModel)` — strict, frozen, extra=forbid; carries
    subject, issuer, serial, not_before, not_after, days_until_expiry,
    severity, warn_threshold_days, critical_threshold_days, evaluated_at.
  - `CertificatePreExpiryError(CertificateError)` — new domain error.
  - `evaluate_loaded_certificate_health(cert, *, warn_days, critical_days, now)` — pure,
    operates on an already-loaded `LoadedCertificate`.
  - `health(path, *, password_env_var, warn_days, critical_days, ...)` — disk
    entry-point; returns `EXPIRED` severity instead of raising on expired bundles.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py` — all new symbols exported.
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_health.py` — 11 colocated `@pytest.mark.unit` tests
  covering OK / WARN boundary / WARN below / CRITICAL boundary / CRITICAL
  below / EXPIRED / disk path / frozen model / error invariants / validation.
- `src/aeat/config.py` — `aeat_cert_warn_days=60`, `aeat_cert_critical_days=14`.
- `env/.env.example` — matching `AEAT_CERT_*_DAYS` entries.
- `src/aeat/application/workflow/_engine.py` — `_classify_cert_expiry` helper; preflight
  stage raises `WorkflowAbortReason.CERT_INVALID` on CRITICAL/EXPIRED,
  logs a warning on WARN, carries `cert_severity` /
  `cert_days_until_expiry` in step details for every severity.
- `src/aeat/application/workflow/test_engine.py` — two new tests
  (`test_cert_pre_expiry_critical_aborts`, `test_cert_pre_expiry_warn_proceeds`)
  plus `_FakeCertificateBundle` parametrisation for subject / not_after /
  fingerprint.
- `src/aeat/entrypoints/cli/doctor.py` — `check_certificate_health` row wired into
  `collect_rows`; CRITICAL/EXPIRED surface as required MISSING (exit 1),
  WARN as advisory WARN, OK as OK.
- `src/aeat/entrypoints/cli/submission/submit.py` — `--force-expiring-cert` flag +
  `_enforce_cert_health` gate. Live submit exits 2 on CRITICAL/EXPIRED
  without the override, prints yellow warning on WARN, proceeds on OK.

## Out of scope (per issue #94)

- `aeat auth health` standalone subcommand — not required by the issue;
  `aeat doctor` already exposes the row.
- Cert rotation / renewal automation.
- Any touch to `aeat.adapters.outbound.aeat.browser`, `aeat.status`, `aeat.application.filing`, or
  `src/aeat/domain/financial/*`.

## Quality gates

- `just lint` — **green**
- `just typecheck` — **green** (ty, not mypy)
- `just test` — **709 passed, 1 skipped, 23 deselected**
- `just hooks` — **green** after one ruff-format pass

## Code review self-audit

- ✅ All new records are strict pydantic v2 (`ConfigDict(strict=True,
  frozen=True, extra="forbid")`).
- ✅ `CertificateHealthSeverity` is `enum.StrEnum`.
- ✅ `CertificatePreExpiryError` inherits from `AeatError` via
  `CertificateError` — test asserts the chain.
- ✅ Logging via `aeat.core.logging.get_logger(__name__)`; no `logging.getLogger`.
- ✅ Public API discipline: `_engine.py`, `doctor.py`, and
  `submit.py` import from `aeat.adapters.outbound.aeat.auth` only, not `aeat.adapters.outbound.aeat.auth.certificate`.
- ✅ No mocks / patches / fakes — tests generate real PKCS#12 bundles
  at runtime and use Protocol-conforming dataclass doubles.
- ✅ Tests carry exactly `@pytest.mark.unit`; colocated under
  `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/` and `src/aeat/application/workflow/`.
- ✅ `env/.env.example` alignment verified by
  `tests/test_config.py::TestEnvExampleAlignment`.
- ✅ `tests/test_release_config.py::test_no_release_please_github_actions_workflow`
  still passes — no `.github/workflows/` file added.
- ✅ Every public symbol carries a Google-style docstring and type hints.
- ✅ Sibling-branch territory untouched.

## Known follow-ups

- Issue #102 (unified `aeat doctor`) will consume the same
  `CertificateHealth` record when it lands — no action needed here.
- When #8 graduates from the `aeat.adapters.outbound.aeat.export._protocols` stub and the
  workflow engine swaps to the rich `aeat.adapters.outbound.aeat.auth.LoadedCertificate`,
  `_classify_cert_expiry` can be retired in favour of
  `evaluate_loaded_certificate_health`.
