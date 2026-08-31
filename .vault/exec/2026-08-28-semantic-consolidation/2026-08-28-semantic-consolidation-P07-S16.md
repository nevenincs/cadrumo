---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:46c92ca136c84bd11a160a666b86b07b03802b26644e5dd3f1ad37c20311f89a'
step_id: 'S16'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the small differently-named export maps in portals, transactions, llm, llm providers, entrypoints and operator_surface, one package per commit

## Scope

- `src/cadrumo/`

## Changes

- `verify:` all five namespaces named by this step are inert; `operator_surface` is a module, not a package

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
