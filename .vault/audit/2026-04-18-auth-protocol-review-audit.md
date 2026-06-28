---
tags:
  - '#audit'
  - '#auth-protocol'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-auth-protocol-research]]'
  - '[[2026-04-18-auth-protocol-adr]]'
  - '[[2026-04-18-auth-provider-abstraction-adr]]'
  - '[[2026-04-18-auth-protocol-plan]]'
---

# `auth-protocol` Code Review

AUTH-PROTOCOL-001 | HIGH | Doctor no longer blocks expired certs and now skips missing-passphrase certs
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py:695-726` now collapses certificate expiry and load failures into `configured=False` / `available=False`, and `src/aeat/entrypoints/cli/doctor.py:617-639` demotes `description.available=False` to `WARN`/`SKIP`. That means an expired cert no longer produces the required failure the previous `health()` path emitted, and a missing `AEAT_CERTIFICATE_PASSWORD_SECRET` is now silently skipped instead of warning the operator.

AUTH-PROTOCOL-002 | MEDIUM | Workflow preflight still treats every provider as certificate-expiring
`src/aeat/application/workflow/_engine.py:817-939` always classifies `certificate.expires_on or today` and records `cert_*` details. A provider description without certificate expiry metadata will be treated as expired and aborted as `CERT_INVALID`, so the new provider-agnostic contract still cannot support non-certificate providers here.

AUTH-PROTOCOL-003 | MEDIUM | Submission CLI health gate remains certificate-only
`src/aeat/entrypoints/cli/submission/submit.py:19-42` returns early unless `description.kind is CERTIFICATE`. That leaves the live-submission health check coupled to the legacy certificate assumption; any future provider will skip the gate entirely instead of being validated against its own health rules.

## Resolution

Follow-up fixes addressed all three findings:

- `AeatAuthenticator.describe()` now preserves missing-passphrase warnings and certificate-health severity details for doctor and submission consumers.
- Workflow preflight now treats missing expiry metadata as provider-specific rather than implicitly expired.
- Submission CLI health gating now evaluates provider availability and severity without a certificate-kind early return.

Independent re-review by the `vaultspec-code-reviewer` persona reported no remaining findings, and the focused regression suite passed with `68 passed, 1 skipped`.
