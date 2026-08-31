---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:1a2a6d373b13748a0d6d13872592a319e3970ee3204f2225acb1d1e02f43ee85'
step_id: 'S141'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Refactor the size-budget subjects in _export_producer.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/filing/_export_producer.py`

## Changes

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->
- `M` `src/cadrumo/application/filing/_export_producer.py`
- `A` `src/cadrumo/application/filing/_producer_ownership.py`
- `M` `src/cadrumo/application/filing/tests/test_export_producer_resolution.py`
- `M` `src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py`

## Notes

```text
uv run --no-sync ruff check src/cadrumo/application/filing/_export_producer.py src/cadrumo/application/filing/_producer_ownership.py src/cadrumo/application/filing/tests/test_export_producer_resolution.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py
All checks passed!
exit 0

uv run --no-sync ruff format --check src/cadrumo/application/filing/_export_producer.py src/cadrumo/application/filing/_producer_ownership.py src/cadrumo/application/filing/tests/test_export_producer_resolution.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py
4 files already formatted
exit 0

uv run --no-sync python -m compileall -q src/cadrumo/application/filing/_export_producer.py src/cadrumo/application/filing/_producer_ownership.py
exit 0

uv run --no-sync pytest -n 0 -o addopts= --collect-only -q src/cadrumo/application/filing/tests/test_export_producer_resolution.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py src/cadrumo/application/filing/tests/test_producer_snapshot.py
63 tests collected in 1.00s
No marker selector or --deselect option was supplied; deselected 0.
exit 0

uv run --no-sync pytest -n 0 -o addopts= -q src/cadrumo/application/filing/tests/test_export_producer_resolution.py
3 passed in 1.46s
exit 0

uv run --no-sync pytest -n 0 -o addopts= -q src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py
12 passed in 2.39s
exit 0

runtime ownership proof: OLD_ROUTE_EXPOSED=False OWNERS=573
exit 0

size proof: _export_producer.py=1145 lines; _producer_ownership.py=47 lines; filing_producer_ownership=15 lines; module limit=1250; callable limit=180.
exit 0

uv run --no-sync pytest -n 0 -o addopts= -q dev/audit/tests/test_codebase_size_budgets.py -k tracked_production_callables_stay_inside_their_declared_band
1 failed, 15 deselected in 25.49s
The 21 reported over-budget callables are outside S141; neither `_export_producer.py` nor `_producer_ownership.py` is named.
exit 1
```
