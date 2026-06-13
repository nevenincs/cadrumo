---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S285-001 | PASS | Active-profile health storage boundary

`src/aeat/application/workflow/_profile_health.py` is an application health and repair
projection over the active profile. It reads active-profile pointers, bucket manifests,
and encrypted profile records through centralized settings, pointer I/O, bucket
manifest helpers, workflow state repositories, and lifecycle services. It does not
define a parallel storage backend or remote-provider mirror.

## S285-002 | PASS | Manifest repair is explicit and bounded

The manifest-status repair path runs only when the assessed status is
`manifest_unreadable`, the active profile is known, and the caller confirms the repair.
It loads the encrypted active profile record before backfilling the plaintext manifest
status through `write_manifest`, preserving the shared bucket manifest contract.

## S285-003 | PASS | Failure paths are surfaced as health states

Exception handling is narrowed to expected storage, validation, manifest, and keyring
failure classes. The projection returns explicit statuses such as `dangling_pointer`,
`manifest_unreadable`, and `profile_record_unreadable`, with compact diagnostic text
where appropriate, instead of silently swallowing degraded state. Best-effort session
opening records the compact error on the returned health snapshot when it cannot
recover.

## S285-004 | PASS | Duplication and validation

Vaultspec RAG clustered this slice with the config repair CLI, active-profile
resolution tests, locale entries for profile repair, and the profile health module
itself. The module reuses shared pydantic health result models, settings, pointer I/O,
manifest helpers, and workflow repositories rather than duplicating those concerns.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/workflow/_profile_health.py src/aeat/application/workflow/test_profile_health.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/test_profile_health.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py::test_config_profile_show_does_not_suggest_switch_for_missing_record`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "active profile health projection manifest status repair next_action settings master key no active bucket session" --type code --port 8766 --max-results 10`

Disposition: close `AFR-183`.
