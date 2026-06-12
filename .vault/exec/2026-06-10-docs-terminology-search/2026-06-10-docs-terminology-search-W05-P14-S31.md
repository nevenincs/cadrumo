---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S31'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Enrol this epic's own architectural vocabulary (Terminology Handbook, sweep, projection, relevance mapping, preprocess hook, laundering, record kinds) as Handbook concepts so build teams cross-reference the ADR definitions through the shipped surface, and keep ADR decision ids D1-D9 cited in every exec record (operator mandate)

## Scope

- `src/aeat/_data/terminology tree + .vault exec discipline`

## Description

- Added approved Terminology Handbook concepts for the epic's architectural vocabulary: `manual-terminologia`, `barrido-rag`, `proyeccion-busqueda`, `mapa-relevancia`, `gancho-preprocesado`, `depuracion-licencia`, and `clases-registro-busqueda`.
- Grounded each new concept in the docs terminology ADR decision ids it names, including D1-D9 coverage across the self-hosting set.
- Related the subordinate architecture concepts back to `manual-terminologia` so `narrower` is derived by the loader rather than authored.
- Added a concept-card projection gate proving the self-hosted concepts are approved and projected into the shipped search/glossary surface with English aliases.
- Confirmed the completed exec records already cite ADR D1-D9 decision ids; the only missing decision-id scan result is the still-open S32 stub, which will be completed in S32.

## Outcome

S31 is satisfied. The epic's own architecture terms are now first-class Handbook concepts and therefore flow through the same generated glossary and concept-card search projection as tax-domain vocabulary. The concepts are approved, carry Spanish ADR-grounded definitions and four-language short descriptions, and project into `ConceptCardRecord` outputs. The curation ratchet remains clean: 115 concepts total, 75 draft, 40 approved, 75 empty short-description backlog entries, still within the 75/75 baseline.

Files touched for this step: `src/aeat/_data/terminology/concepts/terminology-handbook.toml`, `src/aeat/_data/terminology/concepts/barrido-rag.toml`, `src/aeat/_data/terminology/concepts/proyeccion-busqueda.toml`, `src/aeat/_data/terminology/concepts/mapa-relevancia.toml`, `src/aeat/_data/terminology/concepts/gancho-preprocesado.toml`, `src/aeat/_data/terminology/concepts/depuracion-licencia.toml`, `src/aeat/_data/terminology/concepts/clases-registro-busqueda.toml`, `dev/docs/terminology/tests/test_concept_cards.py`, and this exec record.

## Notes

Verification run:

- `uv run pytest src/aeat/terminology/tests/test_loader.py dev/docs/terminology/tests/test_concept_cards.py -q`: 21 passed.
- `uv run pytest src/aeat/terminology dev/docs/terminology -q`: 189 passed, 1 deselected.
- `uv run ruff check src/aeat/terminology dev/docs/terminology`: passed.
- `uv run ruff format --check dev/docs/terminology/tests/test_concept_cards.py src/aeat/_data/terminology/concepts/terminology-handbook.toml src/aeat/_data/terminology/concepts/barrido-rag.toml src/aeat/_data/terminology/concepts/proyeccion-busqueda.toml src/aeat/_data/terminology/concepts/mapa-relevancia.toml src/aeat/_data/terminology/concepts/gancho-preprocesado.toml src/aeat/_data/terminology/concepts/depuracion-licencia.toml src/aeat/_data/terminology/concepts/clases-registro-busqueda.toml`: passed.
- `uv run ty check dev/docs/terminology/tests/test_concept_cards.py`: passed.
- `uv run python -m aeat.terminology audit --ratchet-check`: passed; 115 concepts, 75 draft, 40 approved, 75 empty short descriptions, ratchet clean.
- `uv run pytest src/aeat/tests/test_wheel_bundles_corpus_and_registry.py src/aeat/core/tests/test_resources.py -q`: 22 passed.
- `uv run python -m dev.docs.apidocs scaffold --check`: passed.

`uv run ruff format --check src/aeat/terminology dev/docs/terminology` still reports pre-existing formatting drift in `src/aeat/terminology/_schema.py` and `src/aeat/terminology/tests/test_scaffold.py`; those files were not modified for S31.

The shared worktree still contains unrelated dirty files from other streams. They were not modified for S31.
