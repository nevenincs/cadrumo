---
tags:
  - '#exec'
  - '#modelo-localization-cascade'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:0e3db3585f40a0a72c212f3455d82447d2b240859f2a43d48f9ddaac50b26db5'
step_id: 'S10'
related:
  - "[[2026-08-04-modelo-localization-cascade-plan]]"
---

# Reject live-registry paths and every non-certified production-write mode during migration-app execution

## Scope

- `dev/registry/migration`

## Description

- Verify that no migration-app production-write mode remains in the live tree.
- Verify that new Modelo scaffolding refuses revision-local locale storage.
- Close the historical refusal row against the root-only cutover boundary.

## Outcome

Resolved by absence and by the new-Modelo scaffold guard in
`dev/registry/newmodelo/tests/test_manager.py:52-53`. The deleted disposable
application cannot write the live registry, and new enrollment has no legacy
locale-directory creation path.

## Notes

No compatibility or deprecated write mode was retained.
