---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S75'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-26-secure-storage-test-hygiene-audit]]'
---



# `secure-storage-production-hardening` `W11.P19.S75`

Repaired secure-storage test shortcut coverage by removing platform skip gates from file-mode tests.

## Changes

- Replaced the blob materialisation `skipif` with a real behavior assertion that runs on every platform and checks POSIX mode bits only where POSIX mode semantics exist.
- Replaced the master-key file-mode `skipif` with the same platform-neutral pattern.
- Follow-up review repaired the committed master-key test surface so it is self-contained against the production bucket-DEK and explicit-provisioning implementation.
- Confirmed no `pytest.skip`, `importorskip`, `skipif`, or `xfail` markers remain in the repaired S75 test files.

## Validation

- `uv run ruff check src\aeat\adapters\persistence\storage\blob_store\test_materialisation.py src\aeat\adapters\persistence\storage\master_key\test_master_key.py`
- `uv run pytest src\aeat\adapters\persistence\storage\master_key\test_master_key.py src\aeat\adapters\persistence\storage\blob_store\test_materialisation.py -q`
- `rg -n "pytest\.skip|importorskip|skipif|xfail" src\aeat\adapters\persistence\storage\master_key\test_master_key.py src\aeat\adapters\persistence\storage\blob_store\test_materialisation.py`
