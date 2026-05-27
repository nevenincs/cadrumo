---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
step_id: 'S01'
related:
  - '[[2026-05-27-schema-hardening-m322-standardization-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening-m322-standardization` `P01.S01`

Inventoried the Modelo 322 single-file registry surface and recorded the
mechanical split plan before touching registry data.

- Modified: none
- Created: `.vault/plan/2026-05-27-schema-hardening-m322-standardization-plan.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m322-standardization-inventory.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m322-standardization/2026-05-27-schema-hardening-m322-standardization-P01-S01.md`

## Description

The discovery pass confirmed Modelo 322 is the largest remaining root-level
single-file modelo after M390, with one `2008-y-siguientes` revision and
non-contiguous casilla groups. The intended split mirrors the established
generic directory/fragments layout: manifest-only top-level metadata,
revision metadata in `revision.toml`, and ordered section fragments under the
revision directory.

The scoped pre-edit diff for `src/aeat/_data/registry/aeat/modelos/322.toml`
was empty, so there was no conflicting registry WIP on the split target.

## Tests

Discovery commands only. No registry files were modified in this step.
