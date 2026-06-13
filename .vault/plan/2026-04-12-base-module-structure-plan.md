---
tags:
  - "#plan"
  - "#base-module-structure"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-base-module-structure-adr]]"
  - "[[2026-04-12-base-module-structure-research]]"
---
# Base Module Structure Plan
Date: 2026-04-12

## Plan
1. Create `src/aeat/errors.py` with `AeatError`.
2. Create `src/aeat/logging.py` providing a project logger factory.
3. For each subpackage (`models`, `portals`, `auth`, `schema`, `storage`, `sync`, `browser`, `corpus`, `cli`):
   - Create `src/aeat/<subpackage>/__init__.py`.
   - Add a meaningful docstring to `__init__.py`.
   - Create `src/aeat/<subpackage>/test_smoke.py` validating that the subpackage loads, has a docstring, and optionally exports some placeholder class if necessary.
4. Set up CLI using Typer in `src/aeat/entrypoints/cli/` with a dummy `hello` command.
5. Create `.vault/reference/2026-04-12-base-module-structure-reference.md` (and append/update CLAUDE.md) defining conventions.
6. Run lint, typecheck, tests, and hooks.

## Explicit Plan Review
- **Issue Scope Checks**: Subpackages match exactly (#6 through #17). Tests are colocated, Typed signatures with Google-style docstrings applied. Public API discipline is in place. `AeatError` is the root error. `typer` and `stdlib logging` chosen.
- **Vaultspec Checks**: The plan meets all requirements for standard vaultspec ADR.
- **Review Outcome**: Plan is APPROVED.
