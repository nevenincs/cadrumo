---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-eliminate-shims-audit]]"
---

# audits-resolution group-d step-4

## scope

Plan row D4: replace the certificate-health monkeypatch surface with
a real injection seam.

## changes

`src/aeat/adapters/outbound/aeat/auth/_authenticator.py`:

- New `CertificateHealthCheck` protocol declares the callable
  signature `__call__(path, *, password_env_var, warn_days,
  critical_days, backend=..., friendly_name=..., now=...) ->
  CertificateHealth`. Matches the production
  `certificate_health` function's contract structurally.
- `AeatAuthenticator.__init__` accepts an optional
  `certificate_health_check: CertificateHealthCheck | None`;
  defaults to the module-level `certificate_health` function.
- `describe()` routes through `self._certificate_health_check(...)`
  rather than calling the module-level function directly.

`src/aeat/adapters/outbound/aeat/auth/test_authenticator.py`:

- `test_describe_forwards_bundle_backend_and_friendly_name` flips
  from `monkeypatch.setattr(authenticator_module,
  "certificate_health", ...)` to passing the wrapping
  `_capture_certificate_health` callable directly to
  `AeatAuthenticator(..., certificate_health_check=...)`. The
  wrapper still delegates to the real `certificate_health` for the
  arity / contract checks; no project component is patched.

## verification

`grep -n 'monkeypatch.setattr'
src/aeat/adapters/outbound/aeat/auth/test_authenticator.py` returns
zero matches.

`ruff check` and `ty check` on every touched file: green.

A pre-existing circular import in
`aeat.adapters.outbound.aeat.auth.__init__` prevents direct
collection of `test_authenticator.py` in this branch's snapshot;
the issue reproduces on the clean pre-D4 checkout and is concurrent-
agent territory (the auth package's import topology is in flux from
the CLI-workflow-redesign stream).
