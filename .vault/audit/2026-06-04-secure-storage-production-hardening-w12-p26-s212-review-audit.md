---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
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

## S212-003 | PASS | Filing runtime builder errors are localized

The reviewed module now raises filing-runtime `ModeloBuilderError` instances
with `translated_message` keys and structured contexts. Covered surfaces include
absent modelo lookups, active profile load failures, empty registry roots,
missing requested modelos, empty period-filtered registry selections, blank
modelo selections, partial filing-year/period selectors, provider-year gaps,
revision gaps, and unsupported casilla data types.

The empty-registry context intentionally carries only the registry root name,
not the absolute path, so user-facing formatting has useful context without
leaking local filesystem layout.

## S212-004 | PASS | Validation

- `uv run --no-sync pytest -q src/aeat/application/filing/test_runtime.py` passed.
- `uv run --no-sync ruff check src/aeat/application/filing/runtime.py src/aeat/application/filing/test_runtime.py` passed.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low storage-routing findings
remain for the S212 slice. The raw filing-runtime error-message issue found
during review was fixed in this step rather than deferred.

Disposition: close `AFR-110` as `manifest-discovery`.
