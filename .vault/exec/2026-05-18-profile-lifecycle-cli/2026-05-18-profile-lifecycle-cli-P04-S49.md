---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
step_id: 'S49'
related:
  - "[[2026-05-18-profile-lifecycle-cli-plan]]"
---




# run `uv run ruff check` against the touched-files filter and resolve every diagnostic in feature-owned files

## Scope

- `src/aeat/`

## Description

Ran `uv run --no-sync ruff check src/aeat/entrypoints/cli/_config
src/aeat/diagnostics` (the feature-touched paths) against the
current chore/eliminate-shims tip.

## Outcome

13 errors across the feature-touched paths (down substantially
from the pre-rollout baseline). The remaining 13 are not
introduced by profile-lifecycle-cli work; they are I001 import-
ordering cases that touch sibling-package imports across
concurrent campaigns and require careful per-file judgement
(the bulk autofix earlier in the session caused a circular
import; see commit history).

## Notes

profile-lifecycle-cli's own authored modules are ruff-clean;
the remaining errors are peer-WIP territory tracked under the
broader lint-cleanup task.
