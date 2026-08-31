---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:679556785c09be96fa9373e7219c3c4e9404bae0dbfea144d34d0d34027ad925'
step_id: 'S09'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Census and rule on the second population of namespace export maps the mechanism-name search missed, under different identifiers

## Scope

- `src/cadrumo/`

## Changes

- `verify:` shape-based census of every `__init__.py` for a `__getattr__` or a name-to-submodule dict
- `verify:` four namespaces found; both dict-driven maps use the identifier the original search already covered

## Notes

Censused by SHAPE rather than by identifier, which is the point of the step: a
search for the mechanism NAME cannot find a facade that spells it differently.
The scan looks for a module-level `__getattr__`, or a module-level dict whose
values are all relative submodule strings, in every package namespace.

Four namespaces qualify:

| namespace | dict | size |
| --- | --- | --- |
| `adapters/persistence/storage` | `_LAZY_EXPORTS` | 257 |
| `core` | `_LAZY_EXPORTS` | 357 |
| `entrypoints/cli` | none -- an if-chain | -- |
| `tests` | `_LAZY_EXPORTS` | 2 |

So the feared second population is ONE real member. The two heavy maps use the
same identifier the mechanism-name search already found, and are P01.S07 and
P01.S08. The `tests` facade uses it too and carries two entries.

### The ruling

The one member the identifier search would have missed is
`entrypoints/cli/__init__.py`, whose lazy resolution is an if-chain over name
sets rather than a dict lookup. It is NOT retired on the same grounds as the
other two, and the difference is the reason rather than the mechanism.

The heavy maps exist for namespace convenience -- a caller reaching a contract
through a package instead of its defining module -- which the campaign ruled
against. The CLI one exists to keep `_command_schema`, `_config._google` and
`_modelo_rendering` off the EAGER import path, so constructing the app object
never pulls the registry-dependent command tree; its docstring names the guard
that would be defeated. That is a startup-cost argument about an entrypoint, not
a namespace-shortcut argument, and retiring it would reintroduce the cost.

The `tests` facade is likewise defended in its own docstring, and bounded: "Two
entries are not a migration in progress: a new shared helper belongs in a
submodule, imported by its path, not promoted to a third row here."

Both stay. Recorded so a later sweep reading only the mechanism does not retire
them for consistency with a ruling that was never about them.
