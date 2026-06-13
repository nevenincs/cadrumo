---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S296-001 | PASS | External constants are a read-only remote-mirror registry

`src/aeat/core/external_constants.py` centralizes public third-party hostnames, AEAT
routes, OAuth scopes, MIME strings, encodings, and other externally defined constants.
The only file I/O is TOML read/parse from the packaged registry or an explicit path
parameter. The module does not write files, persist operator data, open secure-storage
repositories, read active profiles, resolve master keys, or call remote providers.

Disposition: close `AFR-194` as `remote-mirror`.

## S296-002 | PASS | Schema consistency is typed and fail-fast where appropriate

The registry is represented by strict frozen Pydantic models with `extra="forbid"`.
AEAT domains, sede paths, portal paths, OAuth scopes, and online service sections are
validated into named models. The volatile Pre303 selector block is deliberately lazy:
registry parsing and `Settings()` construction survive if that block is absent, while
accessing malformed Pre303 constants raises `CoreValidationError` with structured
context.

## S296-003 | PASS | Constant authority has non-tautological guards

The focused tests do not mirror business logic. They parse real modules and real ASTs
to prove executable AEAT route literals, portal paths, MIME strings, encodings,
`CLASSIFIED_BY_MANUAL`, and calculation thresholds route through the central constants
instead of local copies. `Settings.external_constants()` is also tested as the canonical
runtime accessor.

## S296-004 | PASS | Privacy and storage enrollment are bounded

The TOML payload contains public remote identifiers and parser selectors. It does not
contain profile data, NIFs, tokens, passphrases, bucket IDs, SQL routes, or encrypted
records. Because consumers import typed constants rather than reading ad hoc side files,
this surface does not need enrollment in the secure runtime management interface.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/test_hardcoded_constants_inventory.py src/aeat/test_enum_constant_extraction_inventory.py src/aeat/test_latin1_encoding_constant_enrollment.py`
- `uv run --no-sync pytest -q src/aeat/core/test_external_constants.py src/aeat/test_hardcoded_constants_inventory.py src/aeat/test_enum_constant_extraction_inventory.py src/aeat/test_latin1_encoding_constant_enrollment.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "external_constants TOML remote provider constants Settings.external_constants secure storage runtime" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "external constants registry centralizes AEAT URLs OAuth scopes remote API endpoints literal scan" --type code --port 8766 --max-results 8`
