---
tags:
  - '#exec'
  - '#compatibility-lifecycle'
date: '2026-07-09'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e3f8673553d2fdd570385ee1ef3c6756403127f5690af832d08d21fb2ea6ab00'
related:
  - "[[2026-07-09-compatibility-lifecycle-plan]]"
---

# `compatibility-lifecycle` ledger

## Changes

- `S01` `T` `re-export via the aeat.core facade`
- `S01` `T` `src/aeat/core/compatibility_lifecycle.py`
- `S02` `T` `src/aeat/adapters/persistence/storage/tests/test_schema_lineage.py`
- `S03` `T` `src/aeat/core/tests/test_compatibility_lifecycle.py`
- `S04` `T` `src/aeat/tests/test_compatibility_lifecycle_gate.py`
- `S05` `T` `fabricate no old-version fixture`
- `S05` `T` `src/aeat/_data/compat_fixtures`
- `S06` `T` `.vaultspec/rules/compatibility-lifecycle-checkpoint.md`
- `S07` `T` `.claude/rules`
- `S08` `T` `.vault/audit`
