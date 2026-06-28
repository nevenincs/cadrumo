---
tags:
  - "#research"
  - "#base-module-structure"
date: 2026-04-12
modified: '2026-04-12'
related: []
---
# Base Module Structure Research
Date: 2026-04-12
Issue: wgergely/aeat#12

## Purpose
Define the foundational structure of the `src/aeat/` package to accommodate future autonomous agent issues (#6-#11, #16, #17) predictably without merge conflicts.

## Structure Findings
The future issues necessitate the following empty subpackages:
- `models/`: Enums and metadata for tax forms (#6)
- `portals/`: Known AEAT portals and authentication endpoints (#7)
- `auth/`: Cl@ve, certificate logic, and login session management (#8)
- `schema/`: Typed structure definition based on forms (#9)
- `storage/`: Database and historical representation layer (#10)
- `sync/`: Live to local state reconciliation (#11)
- `browser/`: Configurable Playwright session orchestrator (#16)
- `corpus/`: Saved historical tax rules (#17)
- `cli/`: Top-level CLI command routing
- `errors.py`: Single base exception class (`AeatError`)
- `logging.py`: Consistent configured logging factory

## Conventions
- **API Surface**: Explicitly re-exported symbols via `__init__.py`. Other modules must not `import aeat.adapters.outbound.aeat.auth.internal`, but instead `from aeat.adapters.outbound.aeat.auth import Authenticatable`.
- **Testing**: Rust-style colocated tests with explicit `@pytest.mark.unit` markers. No mocks allowed in live tests.
- **Tools**: Typer is present in the dependency tree (from issue 12 dependencies), whereas Click is foundational but Typer offers pydantic integration. `stdlib` vs `structlog` for logging: sticking to standard library logging to keep dependencies thin unless a structlog install is necessary.
