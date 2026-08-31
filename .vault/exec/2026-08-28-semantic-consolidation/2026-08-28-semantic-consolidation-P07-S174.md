---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3dcb1cb4b3bb065a6f81abb7c09bea089f2f658c69bdef6731a2308072441831'
step_id: 'S174'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Relocate the declared error-code tuple out of the errors registry namespace onto a named module, leaving both consumers inside the owning package

## Scope

- `src/cadrumo/core/errors/`

## Changes

- `A` `src/cadrumo/core/errors/registry/declared_codes.py`
- `M` `src/cadrumo/core/errors/error_codes.py`, `src/cadrumo/core/errors/tests/test_registry_enforcement.py`
- `M` `src/cadrumo/core/errors/registry/__init__.py` made inert
- `verify:` `pytest core/errors -n 0 -m ""` -> 54 passed, 1 pre-existing failure naming `application.modelo` exception classes
- `verify:` namespaces defining production code directly: 8 -> 7

## Notes

The registry namespace held one thing: `_ALL_DECLARED_ERROR_CODES`, assembled
from its own submodules. Both consumers -- `error_codes.py` and
`tests/test_registry_enforcement.py` -- sit inside `core.errors`, so repointing
them creates no cross-package private import and needs no ruling. That is why
this one could proceed while the heavier facades cannot.

The relocated name stays private (`_ALL_DECLARED_ERROR_CODES`) inside a public
module. That is deliberate: the tuple is package-internal assembly, its only
external-looking consumer is a test in the same package, and promoting the name
would widen a contract this step has no mandate to widen. `error_codes.py`
keeps its `# pyright: ignore[reportPrivateUsage]` for the same reason.

### The one failure is not this change

`test_exception_base_hygiene` fails on
`ModeloEditSessionClosedError(RuntimeError)` and
`ModeloWorkspaceMaterializationProvenanceMissingError(ValueError)` in
`application.modelo` -- two classes rooting at bare builtins without binding to
the error registry or declaring a rationale. It was failing before this
relocation and is another lane's.

Worth naming because the relocation touched the error registry and the failure
is about error classes: adjacent subject, unrelated cause. Reading the assertion
rather than the file it lives in is what separated them.
