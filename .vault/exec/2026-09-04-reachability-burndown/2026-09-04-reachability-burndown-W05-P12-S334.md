---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:797c9674d02723172eea87d2ef042a6b462d121ca544ea6494fb4b57c1107113'
step_id: 'S334'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the mixed-format container literal census with direct canonical Dockerfile checks

## Scope

- `container base-image tests`
- `canonical resolver behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/packaging/tests/test_container_base_image_singularity.py`
- `A` `dev/packaging/tests/test_container_base_image.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_container_base_image.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
