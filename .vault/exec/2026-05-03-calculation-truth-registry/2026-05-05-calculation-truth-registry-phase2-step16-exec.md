---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `Phase 2` `Step 16`

Removed CLI-owned export header fabrication from the declaration command surface.

- Modified: `src/aeat/entrypoints/cli/_declaration.py`
- Modified: `src/aeat/entrypoints/cli/test_cli_surface.py`
- Modified: `src/aeat/domain/profile/_keys.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The declaration export command no longer branches on a concrete modelo or builds
AEAT record-field headers from draft metadata. It now forwards only explicit
active-profile values normalized into export-header keys. Required header gaps
remain owned by the registry export renderer and fail closed instead of being
filled by CLI defaults.

The declaration calculate and edit commands now translate registry build errors
into CLI boundary errors. The CLI surface test now discovers a registry-backed
modelo that can be calculated from currently available CLI sources, rather than
pinning the command test to a modelo that needs dependent historical input.
Declaration calculation also refuses an active profile without `tax.id` instead
of fabricating a placeholder taxpayer identity.

The taxpayer-profile description for declaration type no longer claims a default
value. Export semantics must come from explicit user data and registry layout
requirements.

The editable profile-key registry now includes `surnames`, allowing the operator
to provide the required export header value declared by current registry layouts.
The filing CLI no longer invents a default profile tax ID or display name when no
profile file is configured.

## Tests

- `uv run pytest src\aeat\entrypoints\cli\test_cli_surface.py::test_app_declaration_calculate_persists_draft src\aeat\application\filing\test_export.py -q`
- `uv run pytest src\aeat\entrypoints\cli\test_cli_surface.py::test_app_declaration_calculate_persists_draft src\aeat\entrypoints\cli\test_cli_surface.py::test_app_declaration_calculate_requires_profile_tax_id src\aeat\entrypoints\cli\test_cli_surface.py::test_app_declaration_calculate_refuses_missing_registry_inputs src\aeat\application\filing\test_export.py -q`
- `uv run ruff check src\aeat\entrypoints\cli\_declaration.py src\aeat\entrypoints\cli\filing\__init__.py src\aeat\entrypoints\cli\test_cli_surface.py src\aeat\domain\profile\_keys.py`
- `uv run ty check src\aeat\entrypoints\cli\_declaration.py src\aeat\entrypoints\cli\filing\__init__.py src\aeat\entrypoints\cli\test_cli_surface.py src\aeat\domain\profile\_keys.py`
- Static discovery over touched runtime surfaces confirmed the removed concrete
  303 record-field names, fabricated operator name, draft-derived NIF headers,
  placeholder tax ID, and declaration-type default are gone from the edited
  command/profile files.
