---
tags:
  - "#adr"
  - "#cert-pre-expiry-gate"
date: 2026-04-13
modified: '2026-04-13'
title: "Certificate Pre-Expiry Health Check + Workflow Gate"
related:
  - "[[2026-04-13-cert-pre-expiry-gate-research]]"
  - "[[2026-04-13-cert-pre-expiry-gate-plan]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-12-workflow-engine-adr]]"
---

# ADR: Certificate Pre-Expiry Health Check + Workflow Gate

## Status
Accepted — 2026-04-13. Implements GitHub issue #94.

## Context

See `[[2026-04-13-cert-pre-expiry-gate-research]]`. The project loudly
fails at `not_after` but does nothing to warn the operator before
expiry, which is unacceptable for a single-workstation autónomo whose
FNMT certificate lives on the same machine that runs the pipeline and
has a 24-month lifetime.

## Decision

### 1 — `CertificateHealth` record

Add a strict pydantic v2 `CertificateHealth` model in
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` (colocated with the existing cert
surface; the issue explicitly targets `aeat.adapters.outbound.aeat.auth.certificate`).

```python
class CertificateHealthSeverity(StrEnum):
    OK = "OK"
    WARN = "WARN"
    CRITICAL = "CRITICAL"
    EXPIRED = "EXPIRED"

class CertificateHealth(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    days_until_expiry: int
    severity: CertificateHealthSeverity
    warn_threshold_days: int
    critical_threshold_days: int
    evaluated_at: datetime
```

Exported from `aeat.adapters.outbound.aeat.auth` alongside `CertificateHealthSeverity`.

### 2 — Severity mapping

Thresholds come from `Settings`:

| Condition                                    | Severity   |
|---                                           |---         |
| `not_after <= evaluated_at`                  | `EXPIRED`  |
| `days_until_expiry <= critical_threshold`    | `CRITICAL` |
| `days_until_expiry <= warn_threshold`        | `WARN`     |
| otherwise                                    | `OK`       |

`days_until_expiry` is computed as
`int((not_after - evaluated_at).total_seconds() // 86400)` and clamped
to negative values for expired certs.

### 3 — Evaluator function

```python
def health(
    path: Path,
    *,
    password_env_var: str,
    warn_days: int,
    critical_days: int,
    now: datetime | None = None,
) -> CertificateHealth: ...
```

Re-uses the existing PKCS#12 loader path but does **not** raise on a
near-expiry or expired cert; callers decide what to do. The function
still raises `CertificateLoadError` / `CertificatePasswordError` for
genuine load failures, because those aren't "pre-expiry" situations.

### 4 — New error

`CertificatePreExpiryError(CertificateError)` — raised by the workflow
gate and CLI when severity is CRITICAL/EXPIRED and no override flag is
passed. Inherits from the existing `CertificateError` → `AeatError`
chain.

### 5 — Settings + env var additions

```
aeat_cert_warn_days: int = 60
aeat_cert_critical_days: int = 14
```

Documented in `env/.env.example`; `tests/test_config.py` kept green via
its existing alignment scanner.

### 6 — Workflow gate

In `aeat.application.workflow._engine.WorkflowEngine._stage_running_preflight`,
after the existing cert `.load()` probe, compute
`CertificateHealth` off the loaded certificate and:

- `EXPIRED` / `CRITICAL` → abort with `WorkflowAbortReason.CERT_INVALID`
  (re-used; the existing reason already covers "cert unusable for
  live submission"). The step summary carries the severity and
  `days_until_expiry`.
- `WARN` → proceed, emit a structured `log.warning` via
  `aeat.core.logging.get_logger(__name__)` naming subject + days-remaining.
- `OK` → proceed silently.

**Rationale for reusing `CERT_INVALID`**: adding a new abort reason
expands the workflow's public enum; the existing reason semantically
already covers "certificate unusable for this submission" and the
`details` dict carries the finer-grained diagnostic
(`cert_severity=CRITICAL`, `cert_days_until_expiry=-3`, etc.). Keeps
the reason catalogue minimal per
`[[2026-04-12-workflow-engine-adr]]`.

Because the engine already loads the certificate via
`CertificateBundleProtocol`, we compute health off the returned
`LoadedCertificate` rather than re-reading the bundle, avoiding a
second PKCS#12 decode. A thin helper
`evaluate_loaded_certificate_health(loaded, *, warn_days, critical_days, now=None)`
is added alongside the path-based `health()` entry point.

### 7 — `aeat doctor` integration

Add a certificate row to `doctor.collect_rows`. When
`settings.aeat_certificate_path` is unset → `State.SKIP`. Otherwise
invoke `health(...)` and map severity:

- `OK` → `State.OK`
- `WARN` → `State.WARN` (required=False)
- `CRITICAL` / `EXPIRED` → `State.MISSING` (required=True, forces doctor exit 1)

Load failures surface as `State.WARN` with the exception class name,
not a crash — the doctor never aborts mid-table.

### 8 — CLI: `aeat submission submit --force-expiring-cert`

Extend `aeat.entrypoints.cli.submission.submit.submit_cmd` with a
`--force-expiring-cert` boolean flag. Before entering the engine,
compute `CertificateHealth` from the configured bundle; if severity is
CRITICAL/EXPIRED and the flag is not set, exit with code 2 and a red
message. WARN prints a yellow warning line and continues.

### 9 — No new `aeat auth health` subcommand

The handover prompt mentioned an `aeat auth health` entry point, but
issue #94 is authoritative and asks for `aeat doctor` + submission
gate. A dedicated subcommand is not required by the acceptance criteria
and would fragment the health surface. Out of scope.

## Consequences

- Operators get at least 60 days of lead time to renew a cert, and a
  hard stop 14 days out.
- `CERT_INVALID` abort semantics expand slightly (now covers "expiring
  soon", not just "load failure"); documented in this ADR and the step
  `details` dict carries the disambiguator.
- Workflow engine takes one extra injected dependency:
  `warn_days` / `critical_days` reach it via the already-injected
  `Settings` instance, so the constructor surface is unchanged.
- Tests add runtime PKCS#12 generation with custom validity windows —
  pattern already established in `test_certificate.py`.

## Alternatives considered

- **New abort reason `CERT_EXPIRING`**: rejected, expands the closed
  enum for no semantic win; `CERT_INVALID` + details suffices.
- **Out-of-band renewal reminder**: rejected, doesn't solve the
  catastrophic-failure case at deadline time.
- **Cron-driven background check**: out of scope for this issue; any
  future scheduler can reuse the `health()` function.
