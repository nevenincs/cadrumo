---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S212]]'
---

# `secure-storage-production-hardening` `W12.P26.S212` Review

## S212-001 | PASS | Filing runtime schema provider is manifest discovery

`runtime.py` resolves registry data through `bundled_path()`,
`Path`-based registry tree fingerprinting, and `ValidatedRegistryAuthority`.
Those reads are bundled registry TOML discovery, not active profile bucket
manifests and not encrypted runtime storage. The module does not construct
secure-object repositories, derive SQL routes, inspect active sessions, or read
environment variables directly.

## S212-002 | PASS | Active profile loading delegates runtime storage

`load_default_filing_profile()` delegates workflow state loading to
`workflow_state_repository()` and active taxpayer projection to the wizard
status surface. It does not create repository instances directly or bypass the
runtime-owned workflow persistence path.

## S212-003 | TRACKED | Filing runtime raw builder messages remain convention debt

The reviewed module still raises several `ModeloBuilderError` instances with
raw English messages. They derive from the AEAT exception hierarchy, but many do
not yet carry `translated_message` keys. This is not a storage-routing defect
for S212; it remains tracked with the broader filing localization remediation
debt already logged by S207.

## S212-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/filing/runtime.py src/aeat/application/filing/test_runtime.py src/aeat/application/filing/test_testing_registry.py` passed.
- `uv run --no-sync pytest src/aeat/application/filing/test_runtime.py src/aeat/application/filing/test_testing_registry.py -q` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low storage-routing findings
remain for the S212 slice. The raw filing-runtime error-message issue is
tracked above as broader convention debt, not closed.

Disposition: close `AFR-110` as `manifest-discovery`.
