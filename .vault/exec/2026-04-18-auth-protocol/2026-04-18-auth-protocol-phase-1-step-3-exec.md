---
tags:
  - '#exec'
  - '#auth-protocol'
date: '2026-04-18'
related:
  - '[[2026-04-18-auth-protocol-plan]]'
---

# `auth-protocol` `phase-1` `step-3`

Migrated the modernized downstream consumers to provider-agnostic auth probes.

- Modified: `src/aeat/submission/_protocols.py`
- Modified: `src/aeat/submission/_preflight.py`
- Modified: `src/aeat/submission/_engine.py`
- Modified: `src/aeat/submission/__init__.py`
- Modified: `src/aeat/cli/submission/_helpers.py`
- Modified: `src/aeat/cli/submission/preflight.py`
- Modified: `src/aeat/cli/submission/submit.py`
- Modified: `src/aeat/cli/doctor.py`
- Modified: `src/aeat/workflow/_protocols.py`
- Modified: `src/aeat/workflow/_engine.py`

## Description

Replaced `CertificateBackend` / `LoadedCertificate` naming in the modernized submission path with `AuthProviderProbe` and `AuthProviderDescription`. Submission preflight now validates provider readiness through `describe()`, `SubmissionEngine` exposes a `preflight()` method over that provider-aware checker, and the live-write gate now centralizes its policy check through `AeatAccessGate.require_live_write()` while preserving the existing safety behavior and audit snapshot flow. The CLI doctor and live submit command now inspect auth readiness through the provider description instead of directly reimplementing certificate health probing.

## Tests

Validated the downstream migration with `uv run pytest src/aeat/submission/test_preflight.py src/aeat/submission/test_engine.py src/aeat/submission/test_safety_helpers.py src/aeat/workflow/test_engine.py src/aeat/cli/_test_doctor.py src/aeat/cli/submission/test_cli.py -q`. The submission, workflow, and CLI suites stayed green after the protocol swap.
