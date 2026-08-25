---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:69f65b7c394d745ceaa0f04ae809602e7463a850729096dcab0cfae3106537b8'
step_id: 'S48'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Relocate reusable terminal widgets behind the components facade

## Scope

- `src/cadrumo/entrypoints/tui/components/widgets.py`
- direct production, development, and test consumers of the moved widgets

## Description

- Move the generic `ContentScroll`, `ContentDataTable`, and `NoticeBand`
  presentation widgets to the canonical widgets module.
- Update every consumer to import directly from `components.widgets`.
- Keep `components/__init__.py` inert; no reexports, aliases, shims, or
  application state are introduced.

## Outcome

The three reusable widget definitions now have one canonical owner in
`components/widgets.py`; `theme.py` retains only palette, CSS, and appearance
helpers. Focused theme/form/status/visual tests pass (53 selected tests), Ruff
and ty pass, and the exact import census shows no package-level component
imports or widget imports from `theme.py`.

## Notes

The first focused run had one transient layout assertion failure in the
overflowing-form test; the isolated rerun and complete focused rerun both
passed. Broader shared-worktree failures remain outside this step's gate.
S48 remains open pending independent review.

Independent review approved S48. The commit also contained registry-data
renames that were pre-staged by an unrelated concurrent worker; those changes
are explicitly outside this step's ownership and were not authored or
reverted here. S48 is now closed in the plan; no S49 work is started.
