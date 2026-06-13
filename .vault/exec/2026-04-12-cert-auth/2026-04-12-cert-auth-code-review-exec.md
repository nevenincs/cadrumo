---
tags:
  - "#exec"
  - "#cert-auth"
date: 2026-04-12
modified: '2026-04-12'
title: "cert-auth code review"
related:
  - "[[2026-04-12-cert-auth-plan]]"
  - "[[2026-04-12-cert-auth-adr]]"
  - "[[2026-04-12-cert-auth-phase1-summary-exec]]"
---

# cert-auth code review

Persona: `vaultspec-code-reviewer` (self-audit; no human in the loop).
Scope: every file touched by issue #8 in the feature/8-cert-auth
worktree. Verdict at the bottom.

## Files reviewed
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/__init__.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_base.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_playwright_context.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_httpx_fallback.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_user_data_dir.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/_mtls_proxy.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py`
- `src/aeat/config.py`
- `env/.env.example`
- `pyproject.toml`

## Checklist

### Backend choice justified
**PASS.** `PLAYWRIGHT_CONTEXT` is the primary backend per the ADR.
Rationale (OS coverage, automation feasibility, AEAT compatibility)
is documented in `.vault/research/2026-04-12-cert-auth-research.md`
§2.1 and the ADR §Decision. `USER_DATA_DIR` and `MTLS_PROXY` are
deferred with explicit ADR rationale; `HTTPX_FALLBACK` is used only
by `verify_handshake`.

### Pydantic v2 strict + frozen
**PASS.** Every boundary record uses
`model_config = ConfigDict(strict=True, frozen=True, extra="forbid")`:
- `CertificateBundle` (certificate.py ~L100)
- `LoadedCertificate` (certificate.py ~L130)
- `HandshakeResult` (certificate.py ~L180)
Unit test `test_bundle_rejects_extra_fields` +
`test_bundle_is_frozen` enforce the mandate at runtime.

### SecretStr never logged, never serialised
**PASS.**
- `CertificateBundle.password_env_var` holds only the *name* of the
  env var, never the value.
- `LoadedCertificate._password` is a `PrivateAttr(SecretStr)`.
- `load_certificate` calls `.get_secret_value()` exactly twice: once
  to hand the bytes to `pkcs12.load_pkcs12`, once to store in the
  PrivateAttr. No other references.
- `HttpxFallbackBackend._export_pem_material` calls
  `.get_secret_value()` exactly once at the re-parse boundary.
- `PlaywrightContextBackend.build_client_certificates_kwarg` calls
  `.get_secret_value()` exactly once at the kwarg-construction
  boundary.
- No `log.*(password)` calls anywhere. All log lines carry public
  metadata only (subject, thumbprint, friendly_name, URL, status).
- `test_loaded_certificate_does_not_leak_secrets` asserts the
  passphrase is absent from `str(dump)`, `model_dump_json()`,
  `repr()`, and `str()`.
- `test_settings_loads_cert_env_vars` asserts
  `SECRET_PASSPHRASE not in repr(settings)`.

### Private-key material outside the pydantic schema
**PASS.** `_pkcs12_bytes`, `_password`, `_private_key_handle` are all
`PrivateAttr` fields on `LoadedCertificate`. They are invisible to
`model_dump`, `model_dump_json`, and the overridden `__repr__`.
Verified by `test_loaded_certificate_does_not_leak_secrets`.

### Typed signatures + Google-style docstrings
**PASS.** Every public function and class has type annotations and
a Google-style docstring. Verified via `uv run ty check src tests`
(clean) and manual inspection.

### Error hierarchy rooted at `AeatError`
**PASS.** `CertificateError(AeatError)` with five subclasses
(`CertificateLoadError`, `CertificatePasswordError`,
`CertificateExpiredError`, `CertificateHandshakeError`). No domain
errors leak `ValueError` / `RuntimeError` across the public boundary.

### Logging via `aeat.core.logging.get_logger`
**PASS.** Every module uses `log = get_logger(__name__)`. No bare
`logging.getLogger` in new code. (The existing `log = logging.getLogger(__name__)`
in `aeat/adapters/outbound/aeat/auth/__init__.py` is pre-existing Google-auth code and is
explicitly out of scope for this issue.)

### Public API discipline
**PASS.** Callers import exclusively from `aeat.adapters.outbound.aeat.auth`; every cert
symbol is re-exported from `aeat/adapters/outbound/aeat/auth/__init__.py` and listed in
`__all__`. Backend implementations live under
`aeat/adapters/outbound/aeat/auth/_certificate_backends/` (leading underscore = private).
`aeat.adapters.outbound.aeat.auth.certificate._select_backend` is the only module that
imports from the backends package.

### Lint / typecheck / tests / hooks
**PASS.**
- `uv run ruff check .` — clean.
- `uv run ty check src tests` — clean.
- `uv run pytest` — 404 passed, 1 skipped, 16 deselected.
- `uv run prek run --all-files` — all hooks green.

### No mocks in integration tests
**PASS.** Every unit test that needs a PKCS#12 bundle generates one
at runtime via `cryptography`. The live test contains zero mocks
and skips cleanly when the cert env vars are absent.

### Tautological / skipped tests
**PASS.** Reviewed all 22 unit tests; each asserts a non-trivial
post-condition. No `pytest.skip` / `xfail` / `ignore` markers
outside the live-test gating, which is the project's standard
opt-in pattern.

### `.env.example` / `Settings` alignment
**PASS.** Five new fields added symmetrically.
`tests/test_config.py::TestEnvExampleAlignment` passes.

## Risks / follow-ups noted
- `aeat.adapters.outbound.aeat.browser.session.BrowserSession` still treats `auth_backend`
  as an opaque stub (see the pre-existing `if self.auth_backend: pass`
  block). Wiring `build_client_certificates_kwarg` into
  `browser.new_context(client_certificates=...)` is explicitly out
  of scope for this issue and is called out in the phase summary.
- `PlaywrightContextBackend.verify` delegates to `HttpxFallbackBackend`
  rather than spinning up a real browser for TLS probes. This is
  intentional (documented in `_playwright_context.py`) but means the
  smoke test does not exercise Playwright's own TLS path. Acceptable
  because the browser-session integration will live-test that path
  end-to-end in its own issue.
- The `_ensure_utc` helper is defensive against a hypothetical
  future downgrade of `cryptography`; the current pin
  (`>=46.0.7`) already returns UTC-aware datetimes from
  `not_valid_before_utc` / `not_valid_after_utc`.

## Verdict
**APPROVED.** No blocking findings. Safe to land.
