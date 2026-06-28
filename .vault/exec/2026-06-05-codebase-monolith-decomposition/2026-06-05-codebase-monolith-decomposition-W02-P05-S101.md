---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S101'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S101 Config Profile Slice Discovery

Scope: `src/aeat/entrypoints/cli/_config/__init__.py`, `src/aeat/entrypoints/cli/_config/tests`, `src/aeat/entrypoints/cli/tests`.

## Description

- Confirm RAG service readiness before selecting the next config profile extraction slice.
- Run semantic search for profile export/import bundle flows and exact search for `config_profile_export`, `config_profile_import`, `_validate_bundle_schema_version`, and `_emit_profile_lifecycle_event`.
- Identify coverage in `test_profile_export_roundtrip.py`, `test_profile_import_idempotency.py`, `test_profile_lifecycle_verbs.py`, and `_config/tests/test_config.py`.

## Outcome

Selected the profile bundle import/export command group for extraction into a focused config submodule. The slice is coherent because it owns portable bundle serialization, bundle parsing, schema-version refusal, import/export lifecycle event emission, and the CLI envelopes for `config profile export` and `config profile import`.

## Notes

Some broad `vaultspec-rag` include-path searches were rejected after PowerShell expanded globs; exact-path semantic searches and direct `rg` discovery provided the usable evidence.
