---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S149'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W06.P21.S149 Semantic CLI boundary closure audit

Scope:
- `vaultspec-rag`
- `src/aeat/entrypoints/cli`
- `src/aeat/application/modelo`

## Description

- Verify `vaultspec-rag` service health.
- Run semantic search for modelo CLI boundary, backend consumer, natural-key, work-unit, calculation-revision, and monolith decomposition concepts.
- Run semantic search for work-calculate input assembly, row validation, casilla/binding overrides, and backend service ownership.
- Run semantic search for extracted projection, compare, export, M036, IVA wallet, and command-registrar surfaces.

## Outcome

- RAG service was healthy on port 8766.
- Semantic results surfaced `_modelo.py` as the remaining transport caller for `calculate_modelo_work_revision`.
- Semantic results surfaced `build_work_calculate_input_bundle` in `application/modelo/_calculate_input.py` as the owner of row validation, casilla normalization, binding splitting, relation parsing, and shortcut application.
- Semantic results surfaced `_modelo.py` registering extracted command modules.
- Semantic results surfaced `_modelo_projection_cli.py`, `_modelo_export_cli.py`, `_modelo_iva_wallet_cli.py`, and application projection services.
- Semantic results surfaced backend `calculate_modelo_work_revision` as the calculation service boundary.
- Semantic results did not identify a duplicate business-logic implementation replacing the application services in the extracted modules.

## Notes

- RAG returned `_modelo.py::_resolve_revision_for_cli` and `_modelo.py` calculate transport snippets as remaining legacy CLI helper surfaces. This is expected residual W06 debt for later command/helper extraction, not a newly added bypass.

Verification:
- `uv run --no-sync vaultspec-rag server service status` - healthy on port 8766.
- `uv run --no-sync vaultspec-rag search "modelo CLI command business logic backend consumer work_unit calculation_revision natural key" --type code --port 8766 --max-results 8 --prefer prod --json` - completed.
- `uv run --no-sync vaultspec-rag search "work calculate CLI build input bundle row validation casilla binding overrides backend service" --type code --port 8766 --max-results 8 --prefer prod --json` - completed.
- `uv run --no-sync vaultspec-rag search "modelo projection compare export m036 iva wallet command registrar application service" --type code --port 8766 --max-results 8 --prefer prod --json` - completed.
