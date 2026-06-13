---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase5` `step17`

Removed the Python modelo metadata registry and old schema extraction/cache
stack as runtime and schema authorities.

- Modified: `src/aeat/domain/calculations/registry/_legal.py`
- Created: `src/aeat/domain/calculations/registry/_citation_blocklist.py`
- Modified: `src/aeat/domain/modelos/__init__.py`
- Modified: `src/aeat/domain/portals/_registry.py`
- Modified: `src/aeat/domain/portals/_cli.py`
- Modified: `src/aeat/domain/casillas/_hydrate/__init__.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`
- Modified: public API docs and README module references for the deleted schema
  extraction packages.
- Deleted: Python modelo metadata entries, metadata models, applicability
  models, citation models, modelo CLI, modelo registry facade, schema cache,
  schema IR, and BOE schema extraction adapter files.

## Description

The current codebase now keeps `aeat.domain.modelos` to the strict
`ModeloCode` identifier surface only. The old Python objects that encoded
modelo metadata, applicability, legal citations, per-modelo entries, and
lookup helpers were removed instead of retained as disabled compatibility
code.

Legal citation blocklist validation moved into the calculation registry so
`verify_legal_catalogue` no longer depends on deleted modelo citation enums or
models. The current legal verification behavior is exercised through the
registry catalogue tests across every preserved known-bad citation row,
diacritic-insensitive matching, and allowed near-miss text.

The old extracted-schema JSON cache and BOE schema extraction adapter were
removed. The current registry schema, loader, source verification, legal
verification, formula runtime, workbook parity, remote-state guard, and portal
model-code cross-reference behavior remain under active tests.

Portal lookup now rejects unknown modelo identifiers with `ValueError`, keeping
portal behavior tied to the current `ModeloCode` enum rather than a removed
modelo registry error hierarchy.

No new migration or prior-state tests were added. The added/changed tests
exercise the current registry validator and current `aeat.domain.modelos`
public surface.

## Tests

- `uv run --no-sync ruff check src/aeat/domain/calculations/registry src/aeat/domain/modelos src/aeat/domain/portals src/aeat/domain/casillas tests/import_contract`
- `uv run --no-sync ty check`
- `uv run --no-sync pytest src/aeat/domain/calculations/registry src/aeat/domain/modelos src/aeat/domain/portals src/aeat/domain/casillas/test_corpus_rule_alignment.py tests/import_contract/test_adr_layout_import_smoke.py tests/import_contract/test_registry_deletion_gates.py`

All passed.
