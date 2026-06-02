---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
step_id: 'S18'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace schema-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Audit registry Python module size and ownership boundaries

## Scope

- `.vault/audit`

## Description

- Inspect the current shared-worktree status for registry production modules.
- Count working-tree and HEAD lines for private production modules under
  `src/aeat/domain/calculations/registry`.
- Identify oversized modules, existing validator extraction state, and dirty
  ownership constraints.
- Record the P04 extraction ordering in a vault audit without editing production
  registry modules.

## Outcome

- The production registry package currently has 70 private production modules,
  21,964 working-tree lines, 10 modules over 500 lines, and 6 modules over
  1,000 lines.
- `_bindings.py`, `_schema.py`, `_record_design.py`, `_applicability.py`,
  `_workbook_parity.py`, and `_formula_runtime.py` are the six modules over
  1,000 lines.
- `_validate.py` has already been split into a validator leaf-module family; the
  largest `_validate_*` leaf measured 359 lines.
- Vault body-link, frontmatter, and plan checks passed.
- `P04.S18` is complete.

## Notes

- The registry package is heavily dirty in the shared worktree. This slice did
  not edit production modules and treated dirty module state as an audit input.
