---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
step_id: 'S63'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S63 Registry Binding Decomposition

Scope: `src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/*.py`.

## Description

- Decompose registry binding-family implementations out of the `_bindings.py` monolith.
- Keep `_bindings.py` as the registry binding facade for historical imports and selector-shape dispatch.
- Add shared selector normalization for binding selectors with injected `source` metadata stripped consistently.
- Move withholding binding implementation into its owning module with an explicit snapshot-time selector validator.
- Preserve package-top-level registry facade imports for application consumers.
- Move application calculation tests from private registry imports to the package facade.

## Outcome

The registry binding module now delegates invoice, ledger, counterpart, detail-record, and withholding binding families to private implementation modules while `_bindings.py` retains the cross-family facade and selector validation dispatch.

Application-facing tests no longer import withholding, observation, or row-resolver symbols from private registry modules.

## Notes

No behavior skips, fakes, mocks, monkeypatches, or xfails were introduced.
