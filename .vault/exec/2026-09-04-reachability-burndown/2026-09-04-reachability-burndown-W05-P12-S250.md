---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:6eb47b1ae532af6ce588e2afd86862e42631f9cb6e99e42fad78861b3b1cac79'
step_id: 'S250'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the test-owned address component vocabulary and its census gate

## Scope

- `Remove the unreachable production constants and self-owning test`
- `correct product prose and the stale disconnected-capability classification`
- `run focused filing gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `D` `src/cadrumo/core/address_components.py`
- `D` `src/cadrumo/core/tests/test_address_component_vocabulary.py`
- `M` `src/cadrumo/core/filing_producer_key.py`
- `M` `src/cadrumo/application/filing/producer_snapshot.py`
- `M` `.vault/reference/2026-09-02-unreachable-capability-disconnected-capability-inventory-reference.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/filing_producer_key.py src/cadrumo/application/filing/producer_snapshot.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/filing/tests/test_producer_snapshot.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py src/cadrumo/domain/calculations/registry/tests/test_export_semantic_vocabulary.py dev/registry/tests/test_modelo_210_party_key_coverage.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
