---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-10-03'
body_hash: 'sha256:3286fc52a75ef6e42695fe3cbfae190d17e33ad0e9335ace63b9a35f43bc6ae1'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S133` Review

## S133-001 | PASS | Google profile binding remains manifest discovery and localizes operator guidance

The reviewed module is a single active-profile resolver for the Google OAuth Desktop integration. It delegates profile identity resolution to the central bucket-pointer precedence chain and raises a typed `GoogleAuthProfileUnboundError` when no profile is active.

It does not persist Google OAuth client, token, or metadata records; construct secure-object repositories; choose local or remote storage providers; route SQL storage; read naked environment variables; or perform direct local file IO. The `manifest-bucket` signal is therefore bounded to manifest discovery.

The user-facing no-active-profile remediation now uses `tr("adapters.google.profile_binding.suggestions.create_profile")` rather than a hard-coded English command string. The locale leaves were created and set through `python -m aeat.locales`, and `python -m aeat.locales audit` reports all locale files clean.

Validation:

- the historical check passed with 6 tests.
- the historical check passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- Source scan found no storage repository constructors, provider selection, SQL route setup, naked environment reads, settings bypass, or direct local file read/write calls in `_profile_binding.py`.

Disposition: close `AFR-031` as `manifest-discovery`.

## S133-002 | MEDIUM | RESOLVED | Locale audit disproved the initial localized-suggestion evidence

The S133 artifact claimed `python -m aeat.locales audit` was clean, but rerunning the audit found the new `adapters.google.profile_binding.suggestions.create_profile` key missing from all four locale catalogues. The resolver test alone was insufficient evidence for catalogue parity.

Resolution: the missing `create_profile` leaf now exists under `adapters.google.profile_binding.suggestions` in `en.yml`, `es.yml`, `ca.yml`, and `hu.yml`.

Validation:

- `uv run --no-sync -q python -m aeat.locales audit` now reports `ca.yml: ok`, `en.yml: ok`, `es.yml: ok`, and `hu.yml: ok`.
- the historical check passed.
