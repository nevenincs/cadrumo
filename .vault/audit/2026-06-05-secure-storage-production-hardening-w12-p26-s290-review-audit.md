---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:0af04bbdfd0ff7a4bc539c9c1c7e6d62cf8bac832cba5da61a5de02ee95b5fbd'
related: []
---

# `secure-storage-production-hardening` Code Review

## S290-001 | PASS | Settings remains the environment authority

The retired module was the project environment authority: AEAT-prefixed
configuration is declared as `Settings` fields and read through `load_settings()` or
`override_settings()`. The S290 gate found one direct `AEAT_OUTPUT_LANGUAGE` write in
The retired module; that generator now pins English through
`override_settings(aeat_output_language="en")` before importing the CLI tree. The
subprocess wrapper still passes environment to the child process as an explicit
process boundary, not as in-process configuration wrangling.

## S290-002 | PASS | Active bucket SQL route is centralized

`Settings._resolve_database_url_for_active_profile()` derives the primary SQLite route
from the explicit database URL, `Settings.aeat_active_profile`, a valid plaintext
active-profile pointer, or the root fallback when no bucket is selected. A present but
invalid pointer no longer degrades to the root fallback. `classify_storage_route()` and
`settings_for_active_profile_bucket()` remain the central route-classification and
named-bucket derivation helpers. Explicit database URLs stay fail-closed for active
bucket derivation.

## S290-003 | PASS | Corrupt pointer fallback is refused and logged

The pointer-read branch in `Settings._resolve_database_url_for_active_profile()` now
logs a debug record with traceback and raises `ActiveProfilePointerError` for a present
invalid pointer. The new route-classification regression writes a real corrupt pointer
file, constructs real `Settings`, verifies the typed refusal, and checks the original
exception is chained.

## S290-004 | PASS | Master-key and remote-provider settings stay declarative

The master-key, secret-store backend, local storage root, blob-store, audit-store,
live-read test opt-in constant, browser cleanup timeout, IVA watchdog timeout, and
outbound storage provider fields remain declarative `Settings` fields. The config
module does not open the secret store, create remote providers, access Google Drive, or
load bucket key material; provider factories, access gates, and master-key loaders
consume these fields downstream.

## S290-005 | PASS | Duplication and runtime rollout coverage

Vaultspec RAG clustered S290 with storage route classification tests,
`settings_for_active_profile_bucket()`, runtime repository route guards, outbound
storage provider settings, master-key provider tests, and active-profile pointer I/O.
No duplicate active bucket SQL route resolver or provider settings surface was found.

Validation passed:

- the historical check
- the historical check
- the historical check
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "Settings active profile pointer database route root fallback debug log secure bucket config" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "aeat core config storage provider google drive secret store backend master key local storage root settings" --type code --port 8766 --max-results 8`

The default pytest lane deselected docs-marker conformance tests. The executed
docs-marker validation was the CLI reference drift test run with `-m docs`.
