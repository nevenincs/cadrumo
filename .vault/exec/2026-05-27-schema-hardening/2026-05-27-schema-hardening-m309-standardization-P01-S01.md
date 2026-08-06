---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-07-17'
body_hash: 'sha256:be502692bc2f01049c156e3b6b597b8c999aa5c828d3e1363f6d055bcf157465'
step_id: 'S01'
related:
  - '[[2026-05-27-schema-hardening-m309-standardization-plan]]'
---

# `schema-hardening-m309-standardization` `P01.S01`

Inventoried the Modelo 309 single-file registry surface and recorded the
mechanical split plan before touching registry data.

- Modified: none.
- Created: `.vault/plan/2026-05-27-schema-hardening-m309-standardization-plan.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m309-standardization-inventory.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m309-standardization/2026-05-27-schema-hardening-m309-standardization-P01-S01.md`

## Description

The discovery pass confirmed Modelo 309 is the largest remaining root-level
single-file modelo, with one `2004-y-siguientes` revision and no existing
directory-form registry source. The intended split mirrors the established
generic directory/fragments layout: manifest-only top-level metadata,
revision metadata in `revision.toml`, and ordered section fragments under
the revision directory.

The scoped pre-edit diff for `309.toml` was empty, so there was no
conflicting registry WIP on the split target.

## Tests

Discovery commands only. No registry files were modified in this step.
