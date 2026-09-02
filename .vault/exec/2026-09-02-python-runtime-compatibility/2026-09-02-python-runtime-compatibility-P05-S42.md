---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:b386fde53ec2c812da02adcc81a31672a2a7d82bc9d781610ab752a27cbc3532'
step_id: 'S42'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Add an inventory-driven local compatibility command

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run python-compatibility; just --dump | Select-String -Pattern 'python-compatibility:|dev.packaging.release_cohort build|dev.ci.python_runtime_compatibility|for mode in source binary|runtime inventory produced no rows'` -> `pass`
- `verify:` `uv run --no-sync python -c 'import json; from dev.ci.python_runtime_matrix import load_runtime_inventory; inventory=load_runtime_inventory(); rows=inventory.rows; assert [row.identifier for row in rows] == ["cp313","cp314","cp315-next"]; assert [row.phase.value for row in rows] == ["stable","stable","prerelease"]; assert rows[-1].blocking is False; print("inventory-driven rows: pass")'` -> `pass`
