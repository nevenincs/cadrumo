---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:553a9cbe182cea816525bb5ae73d452274115fee3052370f920ce71ea347f915'
step_id: 'S66'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the transactions, llm and operator_surface namespaces, the last of the low-risk export maps

## Scope

- `src/cadrumo/`

## Changes

- `verify:` transactions, llm and operator_surface confirmed inert alongside the S16 set

## Notes

Verified rather than assumed: each namespace was checked for relative imports,
class or function definitions, and a non-empty ``__all__``. All five report zero
imports, zero definitions and ``__all__: tuple[str, ...] = ()``.

- `domain/portals`
- `domain/transactions`
- `llm`
- `llm/providers`
- `entrypoints`

`operator_surface` has no package namespace at all -- it is a module,
`_operator_surface_reconciliation.py`, so there was never a map to retire.

One near-miss worth recording. A `grep -c "__getattr__"` on
`llm/providers/__init__.py` returned 1 and read like a surviving lazy arm. The
match is inside the DOCSTRING, which documents the retirement: the package once
"deferred ``AnthropicAdapter`` behind a ``__getattr__`` arm" and the guard
"protected nothing" because its only caller already imported the adapter from its
own module. Counting a mechanism by grepping its name finds the prose about it
too -- the same failure this campaign's shape-based census in P01.S09 was built
to avoid.
