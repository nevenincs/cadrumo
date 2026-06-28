---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S18'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---




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
