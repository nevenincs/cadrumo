---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-07-17'
body_hash: 'sha256:5bc3cdfbad30214e55803716c6bee8246851b4e8078bb765c65b9bf4e84a6964'
step_id: 'S01'
related:
  - '[[2026-05-27-schema-hardening-m190-standardization-plan]]'
---

# `schema-hardening-m190-standardization` `P01.S01`

Inventoried M190 section boundaries and recorded the generic fragment-directory
split strategy before editing registry data.

- Created: `.vault/plan/2026-05-27-schema-hardening-m190-standardization-plan.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m190-standardization-inventory.md`

## Description

M190 is a single-revision modelo stored as one 1,023-line TOML file. The target
layout mirrors the generic M130/M131 fragment substrate: one `manifest.toml`,
one `revision.toml`, and bounded section fragments under the single
`2024-y-siguientes` revision directory.

The source file contains two non-contiguous `bindings` groups, so the split will
preserve those as `bindings` fragment 0001 and 0002 rather than coalescing or
normalizing the data.

## Tests

Validation completed:

- `git diff -- src/aeat/_data/registry/aeat/modelos/190.toml`
- No pre-existing M190 registry diff was present before the inventory step.
