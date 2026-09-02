---
tags:
  - '#exec'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a81daff04005229f03fb122c3d65070ce5ce169e11f559cf06704c99d7d18faf'
step_id: 'S09'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---
# Implement bounded syntax-aware rename transformations with byte-precondition and allowlist enforcement

## Scope

- `dev/quality/object_name_transform.py`

## Changes

- `A` `dev/quality/object_name_transform.py`
- `verify:` `uv run --no-sync ruff check dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ruff format --check dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/quality/object_name_transform.py --output-format concise` -> `pass`
- `verify:` `uv run --no-sync basedpyright dev/quality/object_name_transform.py` -> `pass`
- `verify:` `uv run --no-sync python -m compileall -q dev/quality/object_name_transform.py` -> `pass`
- `verify:` `git diff --check -- dev/quality/object_name_transform.py` -> `pass`

## Notes

Shared-tree concurrency landed the initial transform in `fff7631e84` and its read-only replacement in `d791f14b36` while the assigned S09 executor was working. This closure retains that committed baseline and carries the independent-review remediation.
