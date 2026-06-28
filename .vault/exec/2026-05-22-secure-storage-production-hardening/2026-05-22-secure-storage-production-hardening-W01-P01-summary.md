---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W01.P01` summary

Completed the corrected explicit custody command-surface phase by keeping
custody enrolled through profile lifecycle commands rather than reintroducing
retired top-level config verbs.

- Modified: `src/aeat/adapters/persistence/storage/master_key/_master_key.py`
- Modified: `src/aeat/adapters/persistence/storage/errors.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/_errors.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py`
- Modified: `src/aeat/core/errors/registry/_adapters.py`
- Modified: `src/aeat/application/wizard/_commands.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Created: `src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-22-secure-storage-production-hardening-W01-P01-S01.md`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-22-secure-storage-production-hardening-W01-P01-S02.md`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-22-secure-storage-production-hardening-W01-P01-S03.md`
- Created: `.vault/exec/2026-05-22-secure-storage-production-hardening/2026-05-22-secure-storage-production-hardening-W01-P01-S04.md`

## Description

The master-key read path now fails closed when key material is absent, and
explicit provisioning is available for profile lifecycle create flows. Profile
creation, duplicate, and import paths attempt provisioning before opening a
bucket session, while existing provisioned stores continue normally.

Deprecated operator guidance was corrected across the touched storage surfaces:
the retired config init and top-level custody verb vocabulary was removed from
new hardening artifacts and storage diagnostics. Bucket locked and no-active
suggestions now point at profile lifecycle commands.

The new subprocess test verifies the current operator contract using the file
backend: `profile create` provisions key material, `profile logout` clears the
active pointer, `profile switch` reopens the profile under the same passphrase,
and the retired init surface remains unavailable.

## Tests

Ran:

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py -q`

`uv run --no-sync pytest src/aeat/adapters/persistence/storage/master_key/test_master_key.py -q`

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py -q`

`uv run --no-sync pytest src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py src/aeat/adapters/persistence/storage/master_key/test_master_key.py src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py -q`

Review: mandatory W01.P01 code review reported two medium and one low finding;
the repair re-review reported no remaining findings in scope.
