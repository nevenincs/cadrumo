---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S21'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement synonym-candidate mining with relative-cosine validation and the ratification queue: ratified candidates land in the Handbook as admitted terms or hidden_search_forms through human review under the allowlist-with-reason ratchet

## Scope

- `unratified candidates never reach the shipped index (ADR D6)`
- `dev docs mining + Handbook ratification queue`

## Description

- Added a typed synonym-candidate mining and ratification module for exported embedding observations, with absolute cosine plus relative margin/ratio thresholds.
- Added the developer CLI `python -m dev.docs.terminology.synonyms` with `mine` and `validate` verbs for the committed ratification queue.
- Added the committed ratification queue under `src/aeat/_data/terminology/ratification`, including ratified, proposed, and rejected examples with review reasons where required.
- Tightened the sweep vocabulary enumerator so only preferred/admitted terms and their hidden forms enter the shipped query vocabulary.
- Added gates proving ratified candidates have landed in the Handbook and proposed/rejected candidates are absent from the shipped relevance vocabulary.
- Extended the wheel data packaging guard so terminology data ships with the corpus and registry trees.

## Outcome

S21 is satisfied. Synonym mining now has a CI-safe deterministic layer: raw embedding observations can be filtered into a review queue by relative-cosine validation, and the committed queue is validated against the real Handbook. Ratified candidates must be present as admitted terms or hidden search forms; unratified candidates fail the gate if they appear in the shipped query vocabulary or committed relevance data. The existing `box` query remains shippable through the English preferred term, while the Spanish forbidden row no longer owns the mapping metadata.

Files touched for this step: `dev/docs/terminology/_synonym_mining.py`, `dev/docs/terminology/_synonym_cli.py`, `dev/docs/terminology/synonyms.py`, `dev/docs/terminology/__init__.py`, `dev/docs/terminology/_sweep.py`, `dev/docs/terminology/tests/test_synonym_mining.py`, `dev/docs/terminology/tests/test_sweep.py`, `dev/docs/terminology/tests/test_relevance_data.py`, `src/aeat/_data/terminology/ratification/synonym-candidates.json`, `src/aeat/_data/terminology/relevance/relevance.json`, `src/aeat/tests/test_wheel_bundles_corpus_and_registry.py`, and this exec record.

## Notes

Verification run:

- `uv run pytest dev/docs/terminology/tests/test_synonym_mining.py dev/docs/terminology/tests/test_sweep.py dev/docs/terminology/tests/test_relevance_data.py -q`: 23 passed, 1 deselected.
- `uv run pytest dev/docs/terminology -q`: 85 passed, 1 deselected.
- `uv run python -m dev.docs.terminology.synonyms validate`: passed; 3 candidates clean.
- `uv run ruff check dev/docs/terminology`: passed.
- `uv run ruff format --check dev/docs/terminology`: passed.
- `uv run ty check dev/docs/terminology/_synonym_mining.py dev/docs/terminology/_synonym_cli.py dev/docs/terminology/synonyms.py dev/docs/terminology/_sweep.py dev/docs/terminology/__init__.py`: passed.
- `uv run python -m dev.docs.apidocs scaffold --check`: passed; no API stub drift.
- `uv run pytest src/aeat/core/tests/test_resources.py -q`: 18 passed.
- `uv run pytest src/aeat/tests/test_wheel_bundles_corpus_and_registry.py -q`: 4 passed, proving terminology data is included in the wheel data contract.

`uv run ty check dev/docs/terminology` still reports pre-existing type diagnostics in older terminology tests where fixtures are inferred as `object` despite local `# type: ignore` comments. The changed implementation files pass `ty check` directly.

`uv run vaultspec-core vault plan step check .vault/plan/2026-06-10-docs-terminology-search-plan.md S21` wrote the S21 checkbox and then exited nonzero during graph-cache invalidation because the CLI lacked an initialized workspace context. A subsequent plan status reported 28 of 32 steps complete.

The shared worktree still contains unrelated dirty application and CLI files outside this step. Those were not modified for S21.
