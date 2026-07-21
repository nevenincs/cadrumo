---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S21'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Implement and assert the exact profile-create question count against the decided inventory so an added or dropped question fails the test loudly

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_profile_create_wizard.py`

## Description

- Import the wizard flow through the public `cadrumo.application.wizard` facade
  (`WIZARD_FLOWS`).
- Pin the decided inventory: the exact frozenset of 76 setup-flow question ids and
  the declared count.
- Add a real-behaviour test asserting the flow's declared id set equals the pinned
  set, the declared count equals the unique count (no duplicate ids), and both equal
  the decided size, so an added, dropped, or renamed question fails loudly.

## Outcome

The profile-create prompted-question inventory is now gated. The new test
`test_profile_create_prompted_question_inventory_is_pinned` imports the single
production wizard flow through the package facade, asserts `flow.id == "setup"`, and
compares the declared question-id set against the pinned 76-id frozenset. It also
asserts the declared list length equals both the unique-set length and the decided
count (76), so a duplicate id, an add, a drop, or a same-size rename swap each fail.
No literal count lives in the catalogue: the test is the single enforcement point,
and a legitimate inventory change updates the pinned set in exactly one place.

The test drives the real production flow object (no mock/stub/skip/xfail) and passes
in the integration lane (the module's existing mark, since it shares the interactive
create surface). Ruff check/format and the `ty` type check are clean; the module
collects three tests.

## Notes

Test-only change scoped to one file. The gate runs in the integration lane inherited
from the module rather than the unit lane; it remains a loud CI failure on any silent
question-inventory drift. The import uses the public `WIZARD_FLOWS` facade rather than
dotting into the private catalogue module, per the top-level-reexport ownership rule.
