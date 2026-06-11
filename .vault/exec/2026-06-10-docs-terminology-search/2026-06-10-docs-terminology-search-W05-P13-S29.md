---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S29'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the curation-backlog honesty ratchet: draft-concept and empty-short_description counts gated non-increasing in CI with a standing review cadence, mirroring the locale translation-honesty discipline (ADR D3 consequence)

## Scope

- `terminology audit gate + CI`

## Description

- Verified prior landings `1a9d1608c` and `7d69fdee9` for the curation-backlog ratchet code and tests before changing plan state.
- Kept the committed ratchet baseline at 75 draft concepts and 75 empty `short_description` concepts, sourced from `python -m aeat.terminology audit`.
- Exposed the standing gate through `check_curation_backlog_ratchet()` and `python -m aeat.terminology audit --ratchet-check`.
- Regenerated generated API stubs so `aeat.terminology._ratchet` is represented in the API reference toctree.
- Ran focused terminology gates and API-stub drift checks before closing the step.

## Outcome

S29 is satisfied. The terminology audit now has an executable ratchet that fails on any increase in draft concepts or placeholder/empty short descriptions relative to the committed baseline, while allowing curation progress. The real bundled handbook currently reports 75 draft concepts and 75 empty short descriptions, exactly matching the baseline, and the CLI reports the ratchet as clean.

Files touched for this closeout: `src/aeat/_data/terminology/curation-ratchet.json`, `src/aeat/terminology/_ratchet.py`, `docs/api/aeat.terminology.rst`, `docs/api/aeat.terminology._ratchet.rst`, and this exec record.

## Notes

Verification run:

- `uv run pytest src/aeat/terminology/tests/test_ratchet.py -q`: 6 passed.
- `uv run pytest src/aeat/terminology -q`: 99 passed.
- `uv run ruff check src/aeat/terminology`: passed.
- `uv run ruff format --check src/aeat/terminology/_ratchet.py src/aeat/terminology/tests/test_ratchet.py src/aeat/terminology/cli.py src/aeat/terminology/__init__.py`: passed.
- `uv run ty check src/aeat/terminology`: passed.
- `uv run python -m aeat.terminology audit --ratchet-check`: passed; reported 108 concepts, 75 draft, 33 approved, 75 empty short descriptions, and a clean ratchet.
- `uv run python -m dev.docs.apidocs scaffold --check`: passed after regenerating the missing `_ratchet` API stub.
- `uv run vaultspec-core vault plan check .vault/plan/2026-06-10-docs-terminology-search-plan.md`: passed.

`uv run vaultspec-core vault plan step check .vault/plan/2026-06-10-docs-terminology-search-plan.md S29` wrote the S29 checkbox and then exited nonzero during graph-cache invalidation because the CLI lacked an initialized workspace context. A subsequent plan status reported 27 of 32 steps complete, and plan check passed.
