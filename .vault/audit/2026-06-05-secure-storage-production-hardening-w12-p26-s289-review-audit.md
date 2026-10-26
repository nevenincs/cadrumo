---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:b688aba8aac73d500803c2002359d7b3b251bc3df8e3d4c3b41f72d4bb0454f0'
related: []
---

# `secure-storage-production-hardening` Code Review

## S289-001 | PASS | Access gate is not a storage runtime factory

The retired module exports live-read/write gate types,
authorization-manifest models, and typed access-gate errors. It does not construct
secure-object repositories, select active buckets, scan profile buckets, open SQL
routes, manage master-key material, or call remote storage providers. Runtime bucket
enrollment remains outside this module.

Disposition: close `AFR-187` as a retained plaintext policy/export boundary.

## S289-002 | PASS | Settings owns AEAT live-test configuration

`AeatAccessGate` consumes `settings.aeat_live_tests_enabled` instead of reading
`AEAT_LIVE_TESTS_ENABLED` directly. The settings override tests construct the real
gate from `load_settings()` and prove `override_settings()` controls the gate without
mutating `os.environ`. The only direct environment read is `PYTEST_CURRENT_TEST`,
which is pytest infrastructure, not AEAT application configuration.

## S289-003 | PASS | Authorization manifest failures are typed and loud

The authorization manifest loader parses `authorization.d/<modelo>.toml` fragments
through the shared TOML helper and raises `AuthorizationManifestError` for malformed
fragments, model/stem mismatches, duplicate enrollment, and invalid year claims.
Absent or empty manifest directories remain default-deny-by-absence and do not grant
runtime capability.

## S289-004 | PASS | User-facing live-submit refusal uses central i18n

`LiveSubmitForbiddenError` now uses the centralized
`errors.locked.locked_access_gate_live_submit_forbidden` locale key bound in the
error registry instead of the deprecated `access_gate.errors.default_translatable`
namespace. The obsolete locale leaf was removed through `python -m aeat.locales`, and
`python -m aeat.locales audit` passes for all supported locales.

## S289-005 | PASS | Behavior validation is non-tautological

The added coverage renders a real `LiveSubmitForbiddenError` through the real error
registry and i18n renderer. Existing access-gate and authorization-manifest tests use
real settings overrides, real pydantic models, and real temporary TOML fragments; they
do not mock, monkeypatch, skip, xfail, or mirror production loader logic.

Validation passed:

- the historical check
- the historical check
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "AeatAccessGate Settings live read authorization manifest read_toml no secure bucket repository runtime" --type code --port 8766 --max-results 8`
