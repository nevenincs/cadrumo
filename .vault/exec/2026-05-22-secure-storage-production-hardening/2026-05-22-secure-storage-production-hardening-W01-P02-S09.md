---
tags: ["#exec", "#secure-storage-production-hardening"]
date: "2026-05-22"
modified: '2026-05-22'
step_id: "S09"
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# `secure-storage-production-hardening` `W01.P02.S09`

Rejected explicit database URL writes from normal operator command paths.

- Modified: `src/aeat/entrypoints/cli/__init__.py`

## Description

The CLI active-gate already classified storage routes through `classify_storage_route()`. It now refuses guarded profile-bound mutation verbs when the primary SQL route is `EXPLICIT_DATABASE_URL`, not only when it is the root fallback database.

Bootstrap and recovery paths remain open. The refusal applies only to the existing guarded mutation registry, so profile creation/import, repair probes, help/version, registry reads, and profile switch recovery are not turned into dead ends.

## Tests

Validated with real-entrypoint route-guard coverage in:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_root_fallback_write_guard.py -q`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/__init__.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py`
