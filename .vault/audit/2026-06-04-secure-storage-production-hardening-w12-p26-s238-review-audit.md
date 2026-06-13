---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S238]]'
---

# `secure-storage-production-hardening` `W12.P26.S238` Review

## S238-001 | PASS | Resolver remains manifest discovery

`resolve_profile_sourced_bindings()` loads the user profile through
`UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)` and then
returns an in-memory projection into Decimal, enum, and date binding channels.
The module does not own a storage namespace, plaintext file route, direct SQL
route, environment override, remote provider, or mutation verb.

## S238-002 | PASS | Refusals derive from the core error hierarchy

`ProfileBindingResolutionError` remains a `ModeloError`, which derives from
`AeatError`, and the error class is already registered as
`REFUSED_PROFILE_BINDING_RESOLUTION`.

## S238-003 | PASS | User-facing errors are locale-backed

The profile-binding trace, decimal parse, decimal type, date type, and enum
boolean refusals now pass `translated_message` keys under
`application.modelo.profile_binding.errors.*` with structured context.

## S238-004 | PASS | Profile fact values are not echoed on parse failure

The profile-binding string decimal path keeps the shared decimal parser but
ignores the raw parser message when constructing `ProfileBindingResolutionError`.
The regression test proves an invalid string profile fact does not appear in the
exception text.

## S238-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/modelo/_profile_binding.py src/aeat/application/modelo/test_profile_binding.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/modelo/test_profile_binding.py` passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-136` as `manifest-discovery` with API and privacy
hardening.
