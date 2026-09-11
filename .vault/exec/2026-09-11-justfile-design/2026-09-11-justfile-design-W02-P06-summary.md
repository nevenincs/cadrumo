---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:8f0cde670bc6fd5919846caccd3b56c5b275945173829f7ffd8188a69ebd6d58'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# `justfile-design` `W02.P06` summary

## Changes

- `M` `justfile`
- `A` `dev/registry/analysis/registry_status.py`
- `verify:` `just check-registry` -> `pass`
- `verify:` `just --dry-run report-registry-status` -> `pass`
- `verify:` `just --dry-run report-registry-generated-state` -> `pass`
- `verify:` `just --dry-run registry-publish-authority` -> `pass`
- `verify:` `just --dry-run registry-publish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A` -> `pass`
- `verify:` `just --dry-run registry-republish-target 296 2024-y-siguientes aeat-dr-296-2024 2024 0A EXPECTED_MANIFEST_SHA256` -> `pass`

## Notes

- Legacy generic wrappers remain pending W05 caller migration and removal.
