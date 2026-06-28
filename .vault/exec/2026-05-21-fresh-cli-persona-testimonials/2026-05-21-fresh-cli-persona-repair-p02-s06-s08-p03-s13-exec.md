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

# Fresh CLI persona repair P02/S13 execution

## Closed Steps

- `P02.S06` - formula explanation now emits direct legal and source
  follow-up commands.
- `P02.S07` - Modelo 111 empty required-casilla output now explains the
  practical retention buckets, and readiness output names its preflight
  scope.
- `P02.S08` - Modelo 100 rental-income ledger traceability was documented
  as a capability gap during the design pass.
- `P03.S13` - missing Ley 37/1992 corpus files no longer block registry
  validation or modelo CLI reruns.

## Implementation Notes

- Added `aeat app registry legal view REF` so calculation-registry
  `legal_refs` can be inspected directly without relying on the smaller
  normatives citation catalogue.
- Updated `formulas --explain` legal drill-down lines to use
  `aeat app registry legal view REF`.
- Kept manual/source drill-down conservative: known Renta manual refs
  map to `registry manuals view`; unknown source refs point to
  `registry manuals list`.
- Added Modelo 111 guidance rows for the `casillas 111 --required`
  empty structural set.
- Restored the legal-corpus files required by Ley 37/1992 refs for
  articles 94, 95, 122, 123, and 124.

## Verification

- `uv run ruff check src/aeat/application/registry/__init__.py src/aeat/entrypoints/cli/registry.py src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py src/aeat/entrypoints/cli/test_registry_cli.py src/aeat/entrypoints/cli/test_modelo_discovery_defects.py src/aeat/core/errors/registry/_domain.py`
- `uv run pytest src/aeat/entrypoints/cli/test_modelo.py::test_formulas_explain_emits_reference_drill_down_commands src/aeat/entrypoints/cli/test_modelo.py::test_modelo_111_required_casillas_explain_practical_empty_set src/aeat/entrypoints/cli/test_modelo_discovery_defects.py::test_modelo_readiness_names_preflight_scope src/aeat/entrypoints/cli/test_registry_cli.py::test_registry_legal_view_resolves_formula_legal_ref -q`
- `uv run python -m aeat.locales audit`
- `uv run python -m aeat.locales scaffold --check`
- `uv run aeat app registry verify`
- `uv run aeat app modelo formulas 111 --period 1T --explain`
- `uv run aeat app modelo formulas 303 --period 1T --explain`
- `uv run aeat app modelo casillas 111 --required`
- `uv run aeat app modelo casillas 303 --period 1T --form-number 69`
