---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:5ffe67577de9e0b8fa659254b74065c61f52f9bfd52a15a90f8dfe3798516733'
step_id: 'S61'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Expose registry authority publication target publication and republish mutations as separate recipes

## Scope

- `justfile`

## Changes

- `M` `justfile`
- `verify:` `just --dry-run registry-publish-authority` -> `pass`
- `verify:` `just --dry-run registry-publish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A` -> `pass`
- `verify:` `just --dry-run registry-republish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A EXPECTED_MANIFEST_SHA256` -> `pass`
