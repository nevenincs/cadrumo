---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:955d2a45e6277399a0584031c9c6bd61af56cb164ffcb5ed7a32215a5db7b61c'
step_id: 'S02'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Consolidate environment installation and optional workstation provisioning behind distinct setup operations

## Scope

- `dev/env`

## Changes

- `M` `dev/env/__init__.py`
- `M` `dev/env/__main__.py`
- `M` `dev/env/playwright_doctor.py`
- `verify:` `just --dry-run setup` -> `pass`
- `verify:` `just --dry-run setup-workstation-tools` -> `pass`
- `verify:` `just --dry-run setup-browser` -> `pass`
