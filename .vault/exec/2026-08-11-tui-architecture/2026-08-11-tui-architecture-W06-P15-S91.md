---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:70a6791256abdafde700a00343c0a9e82949cdc71a6cd56fa796070d42816b40'
step_id: 'S91'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove zero production or shared-test imports of the TUI, zero Textual outside its root, and a fully importable canonical package

## Scope

- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Changes

M dev/tests/test_import_hygiene_gate.py

## Notes

The Step row cites src/cadrumo/tests/test_import_hygiene_gate.py; the gate lives at
dev/tests/test_import_hygiene_gate.py, which the architecture rule places outside the src
test lanes deliberately. Code takes precedence, so the assertions landed there.

The whole-tree sweep found three real reaches, all function-local CLI launch seams into the
TUI view hosts. Those are the intended direction and were declared with reasons rather than
rewritten. Textual containment and canonical-package importability needed no exemption.
