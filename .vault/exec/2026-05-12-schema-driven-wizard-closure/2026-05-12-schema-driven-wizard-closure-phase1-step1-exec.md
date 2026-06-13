---
tags:
  - '#exec'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-closure-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# c1 sweep stale invocation-form docstrings

## scope

C1 rewrites three module docstrings so they describe the surface
under its current invocation path (`aeat app archive`,
`aeat app topic`). The references to the deleted `aeat archive`,
`aeat topic`, and `aeat help <slug>` forms are excised. C3 handles
the `UX-015 closure.` line on `_topic.py:3` in a separate commit.

## files owned

- `src/aeat/entrypoints/cli/_archive.py` — module docstring header
  and verb examples migrated to `aeat app archive ...`
- `src/aeat/entrypoints/cli/_topic.py` — module docstring first line
  rewritten; the `aeat help <slug>` reference removed
- `src/aeat/application/topics/__init__.py` — module docstring's
  invocation examples migrated to `aeat app topic`; the
  `aeat help <slug>` alias line removed (the alias no longer exists)

## acceptance gates run

- `grep -rn 'aeat archive\b|aeat topic\b|aeat help <?slug'
  src/aeat/entrypoints/cli/_archive.py
  src/aeat/entrypoints/cli/_topic.py
  src/aeat/application/topics/` — returns nothing
- `ruff check src/aeat/entrypoints/cli/_archive.py
  src/aeat/entrypoints/cli/_topic.py
  src/aeat/application/topics/__init__.py` — passes
- `ty check src/aeat/entrypoints/cli/_archive.py
  src/aeat/entrypoints/cli/_topic.py
  src/aeat/application/topics/__init__.py` — passes

## notes

The underlying Typer command names are unchanged; only the human-
readable docstrings move. The `UX-015 closure.` legacy-marker line
in `_topic.py:3` stays untouched here and is excised by C3 together
with the `_storage_namespaces.py` and `_profiles.py` transient-meta
violations.
