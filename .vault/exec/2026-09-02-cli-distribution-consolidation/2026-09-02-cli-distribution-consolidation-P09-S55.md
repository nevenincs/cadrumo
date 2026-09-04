---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:e8826abc5b7722072a0a28b25a3e61f691b47a6fbf75ed52a9641541aa8a753e'
step_id: 'S55'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Give the hand-assembled cohort fixtures the wheelhouse the manifest requires

## Scope

- `packaging/homebrew/tests/test_homebrew_generate.py`

## Changes

- `M` `dev/packaging/tests/test_smoke_core_payload.py`
- `M` `packaging/scoop/tests/test_scoop_generate.py`
- `M` `packaging/homebrew/tests/test_homebrew_generate.py`

## Notes

The three fixtures assembled a cohort without the runtime wheelhouse the
manifest requires, so the loader refused each one before any assertion in
those tests ran. Two of them also hand-rolled a source archive carrying no
lock at all, which would have failed the next check even once the wheelhouse
landed; both now route through the paired helpers, whose archive and
wheelhouse bind to the same lock by construction.

Repairing the fixtures made three assertions reachable for the first time,
and all three fail. That is a strictly better state than the refusal that hid
them, not a regression introduced here, and the three are tracked separately.
One of them contradicts a generator change made earlier in this campaign and
could never have passed since; it went unseen because a different refusal
fired first, which is what a suite too slow to run locally costs.

## Scope

- `packaging/homebrew/tests/test_homebrew_generate.py`

## Changes
