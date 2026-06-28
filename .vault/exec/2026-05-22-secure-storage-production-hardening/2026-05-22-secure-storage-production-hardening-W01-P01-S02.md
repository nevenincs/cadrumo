---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S02'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening` `W01.P01.S02`

Wired explicit custody provisioning into the existing profile lifecycle create
paths without adding deprecated top-level config custody verbs.

- Modified: `src/aeat/application/wizard/_commands.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

`profile create` now provisions master-key material explicitly before opening
the bucket session for the first encrypted profile write. Existing provisioned
state is accepted for follow-on create-like flows by catching the typed
already-exists storage error.

The atomic profile creation helper used by import and duplicate now also
attempts explicit provisioning before opening the target bucket session. This
keeps profile lifecycle operations as the custody surface and avoids the
retired `config init` command shape.

## Tests

Ran:

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_custody_profile_lifecycle.py -q`

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/test_profile_create_taxpayer_type_paths.py -q`

Result: 1 passed for the new custody test, and 51 passed for the existing
profile lifecycle slice.
