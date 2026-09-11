---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:3e06eddebd32666aa5c01871461de172565349daf54bd643968b9c0d54fd5e23'
step_id: 'S52'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Preserve repository tooling inside minimal setup while keeping workstation and browser provisioning optional

## Scope

- `dev/init`

## Changes

- `M` `dev/init/README.md`
- `M` `dev/init/plan.py`
- `verify:` `just --dry-run setup` -> `pass`
- `verify:` `just --dry-run setup-workstation-tools` -> `pass`
- `verify:` `just --dry-run setup-browser` -> `pass`
