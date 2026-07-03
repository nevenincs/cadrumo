---
tags:
  - '#exec'
  - '#arch-remediation-lazy-import-policy'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S02'
related:
  - "[[2026-07-02-arch-remediation-lazy-import-policy-plan]]"
---

# Implement the classifier gate that walks production modules, collects function-local first-party imports, and structurally recognises the five sanctioned classes: core resource-repository loaders, PEP 562 CLI cold-start deferrals, TYPE_CHECKING blocks, optional third-party dependency guards, and adapter heavy-import deferrals

## Scope

- `src/aeat/tests/test_lazy_import_policy.py`

## Description

- Implement the classifier gate walking every production module via the shared `_inventory` AST helpers (real `ast`, no mocks).
- Recognise the five sanctioned classes structurally: `TYPE_CHECKING` blocks and `try/except ImportError` guards inside the `_ScopeWalker`; PEP 562 `__getattr__` bodies, the `entrypoints/cli/` cold-start subtree, and the `core/resources/` loader subtree in the discovery pass.
- Resolve each function-local import to its runtime-graph edge, resolving relative imports against the containing package exactly as Python does.

## Outcome

`_discover_unsanctioned_sites` returns only the unsanctioned first-party function-local import surface. The walk reproduces the frozen baseline exactly (`test_discovery_is_non_empty_and_reproduces_baseline` green).

## Notes

Fixed a relative-import resolution defect during authoring: the containing package for a package `__init__` is the package itself, so resolving against `rel_parts[:-1]` uniformly (dropping the module name or `__init__`) is required to match Python semantics.
