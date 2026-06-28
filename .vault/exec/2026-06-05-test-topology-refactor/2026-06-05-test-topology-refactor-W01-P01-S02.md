---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S02'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P01.S02`

## Scope

Relocation ownership inventory for package-local movement.

## Description

- Classified naked package-root tests as cross-cutting tests owned by `src/aeat/tests`.
- Classified `src/aeat/locales` tests as cross-cutting locale/tooling tests owned by `src/aeat/tests`.
- Classified architectural package tests by nearest package owner: `domain`, `application`, `adapters`, `entrypoints`, and `core`.
- Classified deep package tests by their current parent package, with relocation to a child `tests` directory under that same owner.

## Outcome

- The relocation rule is mechanical: each test file moves from its current owning package directory into a sibling `tests` child directory.
- Package-root and locale tests are the explicit exceptions and move into `src/aeat/tests`.
- Underscore-prefixed CLI privacy and envelope tests are renamed to `test_*.py` while moving into `src/aeat/entrypoints/cli/tests`.

## Notes

- Inventory is ownership-based; it intentionally avoids preserving campaign labels as durable grouping metadata.
