---
tags:
  - '#exec'
  - '#user-profile-lazy-import'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S02'
related:
  - "[[2026-06-03-user-profile-lazy-import-plan]]"
---

# Trace the registry-pull chain from the application boundary

## Scope

- `src/aeat/application/user_profile/__init__.py`
- `src/aeat/domain/user_profile/__init__.py`

## Description

- Probe the application package's registry-pull contribution in a fresh
  interpreter (`python -c "import sys; import aeat.application.user_profile;
  ..."`); record the count at 69.
- Inspect the boundary `__init__.py`: confirm the top-level
  `from ...domain.user_profile import (...)` block and the 17 Pydantic
  model declarations whose field types reference those records.
- Confirm Pydantic v2 resolves field types at class-creation time, so
  the domain-record import cannot move into the existing `__getattr__`
  block while the models stay in the boundary body.
- Note: the domain `__init__.py`'s eager pull of `_registry_contract`
  is treated as in-scope-for-the-domain per the ADR's hexagonal-direction
  rule; the application-layer fix targets the application boundary.

## Outcome

- Chain confirmed: application boundary's 17 Pydantic models force eager
  import of the four domain records, which transitively pulls
  `_registry_contract` and the 69-submodule registry slice.
- Relocation target identified: `_commands.py` sibling module, with the
  PEP 562 `__getattr__` block extended to re-export the relocated names
  and the four domain records on demand.

## Notes

- Discovered during P02 execution that the same 69-module pull is also
  produced by `aeat.entrypoints.cli._errors` independently of the
  application-boundary fix (it imports from `aeat.domain.user_profile`,
  whose package `__init__.py` triggers `_registry_contract`). This is the
  orthogonal regression vector recorded in the ADR's Findings section.
