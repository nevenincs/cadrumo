---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
step_id: 'S09'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening` `P03.S09`

Added regression coverage for the approved `sin` boundary and the committed
singleton metadata.

- Modified: `src/aeat/domain/calculations/registry/test_semantic_role.py`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P03-S09.md`

## Description

The tests now assert that unmarked `con`/`sin` maintenance-employment roles are
not axis siblings and should warn, while the reviewed committed rows must carry
explicit singleton metadata and stay warning-clean after registry load.

## Tests

Covered by the P03.S10 gate record.
