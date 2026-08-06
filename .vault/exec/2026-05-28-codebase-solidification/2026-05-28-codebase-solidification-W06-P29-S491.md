---
step_id: S491
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-31
modified: '2026-07-17'
body_hash: 'sha256:3d3da1fd7d8526d9e28cf7d9a5cf25f0b03f45327ed726f62ce4819423852eb4'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P29.S491

**Step**: introduce UTF_8_ENCODING constant in external_constants and selectively migrate encoding="utf-8" call-sites.

## Outcome

- `UTF_8_ENCODING: Final[str] = "utf-8"` added to `aeat.core.external_constants`
- `_envelope.py`: 5 `encoding="utf-8"` sites migrated to `encoding=_UTF_8_ENCODING`
- `_manifest_io.py`: 2 sites migrated
- `application/registry/__init__.py`: 2 sites migrated (sibling discovery)

## Files

- `src/aeat/core/external_constants.py`
- `src/aeat/adapters/persistence/storage/envelope/_envelope.py`
- `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`
- `src/aeat/application/registry/__init__.py` (sibling)

## Commit

5b45dd58c
