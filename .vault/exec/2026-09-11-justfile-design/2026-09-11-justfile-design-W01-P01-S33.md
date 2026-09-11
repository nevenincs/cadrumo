---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:3f15407be41c329142608255f2dffd4fb1dc30e141ef2c41c680666f1630a410'
step_id: 'S33'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Preserve clean preview and destructive application as an isolated non-aggregated pair

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run clean; just --dry-run clean-apply` -> `pass`
