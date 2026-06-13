---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S01'
related:
  - '[[2026-05-27-schema-hardening-m390-standardization-plan]]'
---

# `schema-hardening-m390-standardization` `P01.S01`

Inventoried M390 section boundaries and recorded the generic fragment-directory
split strategy before editing registry data.

- Created: `.vault/plan/2026-05-27-schema-hardening-m390-standardization-plan.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m390-standardization-inventory.md`

## Description

M390 is a single-revision modelo stored as one 808-line TOML file. The target
layout mirrors the generic M115/M720 fragment substrate: one `manifest.toml`,
one `revision.toml`, and bounded section fragments under the single
`2010-y-siguientes` revision directory.

The source file contains two non-contiguous `casillas` groups, so the split will
preserve those as `casillas` fragment 0001 and 0002 rather than coalescing or
normalizing the data.

## Tests

Validation completed:

- `git diff -- src/aeat/_data/registry/aeat/modelos/390.toml`
- No pre-existing M390 registry diff was present before the inventory step.
