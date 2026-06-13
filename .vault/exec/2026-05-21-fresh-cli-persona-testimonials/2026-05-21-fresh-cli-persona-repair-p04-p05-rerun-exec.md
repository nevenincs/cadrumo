---
tags:
  - '#exec'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-fresh-cli-persona-repair-plan]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory-audit]]'
---

# Fresh CLI persona repair P04/P05 rerun

## Focused Reruns

- Ana reran Modelo 303 formula explanation. Legal drill-down was usable,
  but source refs still pointed only to `registry manuals list`.
- Bruno reran Modelo 111 guidance. `casillas 111 --required` was useful,
  and formula explanation exposed follow-up commands. Shared-profile
  readiness was blocked by an undecryptable stored draft object.
- Clara reran the repaired defects in an isolated state root. Casilla 69
  lookup, filing/verification report lists, work create/calculate, and
  the retired `SecureObjectUnreadable` import path behaved correctly.

## Follow-Up Repairs

- Added `aeat app registry sources view REF` for direct source-reference
  inspection.
- Updated `formulas --explain` so non-manual source refs emit
  `aeat app registry sources view REF`.
- Triaged readiness integrity: clean isolated readiness for Modelo 111
  succeeds with `ready True`; the shared-root failure is an existing
  secure-object decryptability condition with recovery
  `aeat config repair integrity objects`.

## Verification

- `uv run aeat app registry sources view aeat-dr-303-2025`
- `uv run aeat app modelo formulas 303 --period 1T --explain`
- `uv run aeat app modelo readiness --modelo 111 --revision-id 2019-y-siguientes --year 2026 --period 1T` in a clean isolated `AEAT_LOCAL_STORAGE_ROOT`
- `uv run ruff check src/aeat/application/registry/__init__.py src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_registry_cli.py`
- `uv run pytest src/aeat/entrypoints/cli/test_modelo.py::test_formulas_explain_emits_reference_drill_down_commands src/aeat/entrypoints/cli/test_modelo.py::test_modelo_111_required_casillas_explain_practical_empty_set src/aeat/entrypoints/cli/test_registry_cli.py::test_registry_legal_view_resolves_formula_legal_ref src/aeat/entrypoints/cli/test_registry_cli.py::test_registry_sources_view_resolves_formula_source_ref -q`
- `uv run python -m aeat.locales audit`
- `uv run python -m aeat.locales scaffold --check`
