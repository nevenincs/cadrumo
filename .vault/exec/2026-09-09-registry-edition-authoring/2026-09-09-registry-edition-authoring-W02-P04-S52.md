---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:93862aa26a8f4c97cbcfb0295bef9212240f9e73f8db8cf263ea78d813d24079'
step_id: 'S52'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [M | opus-medium] Fix candidate staging, which copies a predecessor's raw casilla directory wholesale and would therefore copy a DELTA rather than an edition once the predecessor is migrated. It also walks the continuity-evolution chain rather than the edition-inheritance chain, so under this decision it follows the wrong relationship. Proof: staging a candidate from a migrated predecessor produces a complete edition, and the chain it walks is the declared predecessor chain.

## Scope

- `dev/registry/pipeline/candidate_staging.py`

## Changes

- `M` `dev/registry/pipeline/candidate_staging.py`
- `A` `dev/registry/tests/test_continuity_witness_staging.py`
- `verify:` `uv run --no-sync pytest test_continuity_witness_staging.py` -> `pass`
- `verify:` `uv run --no-sync pytest test_continuity_witness_staging.py` against the HEAD `candidate_staging.py` -> `fail` (3 of 5)
- `verify:` HEAD-versus-new `stage_continuity_metadata` byte comparison over all 128 live modelo targets -> `pass`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass`
- `verify:` `uv run --no-sync ruff check`, `ruff format --check`, `ty check` on the two files -> `pass`
- `verify:` `uv run --no-sync pytest test_continuity_witness_staging.py test_isolated_edition_staging.py test_generated_tree_cli.py test_generated_export_trees.py test_m303_generated_envelope_proof.py` -> `fail` (1 pre-existing)

## Notes

- `test_absent_tree_is_validated_then_published_through_the_canonical_authorities` fails on the modelo 184 seeded-lineage refusals recorded under S56; it predates this change.
- `stage_generated_export_candidate` still prunes the target's siblings, so a delta target stages without its predecessor and the candidate load refuses it. Left unchanged: materialising the candidate target decides where inherited rows' generated export references are written, which is S51's decision.
- A reviewed delta edition carrying `reviewed_against` cannot be staged standalone by either staging path: `materialise_edition` drops `predecessor` but keeps `reviewed_against`, which the governance validator refuses on an edition naming no predecessor. No live edition is affected yet.
- The reviewer persona could not be launched from this session, so the review is still outstanding.

- The reviewer persona could not be launched. The orchestrating session reviewed the diff: staging resolves through `materialise_edition` with no second walk, and unmigrated modelos take an unchanged path. Re-run: 10 passed, ruff and ty clean, no underscore import from `src`. Staging a delta candidate target is left to S51, and the `reviewed_against` interaction was handed to S53.
