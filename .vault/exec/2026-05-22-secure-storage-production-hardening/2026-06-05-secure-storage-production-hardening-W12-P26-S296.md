---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S296'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S296 - Close AFR-194 for external constants

Scope: close `AFR-194` for `src/aeat/core/external_constants.py` with signals
`plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `external_constants.py` as the central typed registry for third-party
  hostnames, AEAT service paths, OAuth scopes, MIME strings, encodings, and remote
  endpoint constants loaded from `external_constants.toml`.
- Confirmed the module is read-only: it parses the packaged TOML registry or an
  explicit caller-supplied path, validates frozen strict Pydantic models, and does not
  write files, mutate environment variables, open storage runtime sessions, or call
  remote providers.
- Confirmed volatile Pre303/IVA-wallet selector validation is lazy and wrapped in
  `CoreValidationError`, so malformed remote web-scraping constants do not poison
  unrelated `Settings()` construction.
- Verified the existing tests guard centralization without duplicating business logic:
  route literal scans, portal path ownership, MIME/encoding/sentinel single-source
  checks, and `Settings.external_constants()` identity coverage.
- Ran vaultspec RAG searches for duplicate external-constant and remote-provider
  authority surfaces.

## Outcome

`AFR-194` is closed as `remote-mirror`. The file remains a retained plain-file registry
reader and remote-provider constant authority, not a secure-storage persistence surface.
No production code change was required for this row.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/test_hardcoded_constants_inventory.py src/aeat/test_enum_constant_extraction_inventory.py src/aeat/test_latin1_encoding_constant_enrollment.py`
- `uv run --no-sync pytest -q src/aeat/core/test_external_constants.py src/aeat/test_hardcoded_constants_inventory.py src/aeat/test_enum_constant_extraction_inventory.py src/aeat/test_latin1_encoding_constant_enrollment.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "external_constants TOML remote provider constants Settings.external_constants secure storage runtime" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "external constants registry centralizes AEAT URLs OAuth scopes remote API endpoints literal scan" --type code --port 8766 --max-results 8`

## Notes

The `plain-file` signal is accepted because the module reads the packaged
`external_constants.toml` registry. That registry contains externally defined public
routes and selectors, not operator profile data, secrets, bucket identifiers, or
encrypted application records.
