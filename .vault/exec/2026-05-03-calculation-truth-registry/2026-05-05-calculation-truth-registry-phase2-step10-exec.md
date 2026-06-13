---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase2` `step10`

Removed remaining application-surface test and schema fallbacks that restated
old draft schema state instead of exercising registry-backed behaviour.

- Modified: `src/aeat/application/filing/test_schema_completeness.py`
- Modified: `src/aeat/application/workflow/_engine.py`
- Modified: `src/aeat/application/workflow/_models.py`
- Modified: `src/aeat/application/workflow/test_models.py`
- Modified: `src/aeat/application/workflow/test_engine.py`
- Modified: `src/aeat/application/review/test_aggregator.py`
- Modified: `src/aeat/application/review/test_adapters.py`
- Modified: `src/aeat/domain/filing/_schema.py`
- Modified: `src/aeat/domain/filing/__init__.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`test_schema_completeness.py` no longer hardcodes Modelo 130 casilla counts,
formula input tuples, or application-link identifiers. It now derives
formula-bound casillas and expected casilla references from the registry
snapshot expression graph, then verifies the runtime provider exposes the
same projection.

`test_models.py` no longer mirrors workflow enum members. The retained
coverage exercises hash stability, pydantic validation, site-health alert
records, terminal-result invariants, and JSON round-trips. `_models.py`
docstrings now describe stable diagnostics behaviour instead of treating enum
ordering as a standalone test target.

`_engine.py` now resolves the active registry schema for the workflow
obligation period and requires exact schema-version equality before draft
validation or preflight. Workflow tests cover wrong-model schema namespace and
same-model inactive revision failures.

The unused `SCHEMA_VERSION_DEFAULT` fallback was removed from the filing
domain schema and public exports. Remaining tests that carried the old
fallback string now derive active registry schema values from the runtime
provider.

## Tests

- `rg -n "SCHEMA_VERSION_DEFAULT|filing-schema-0\\.1\\.0|ad hoc collection" src tests`
  returned no matches.
- `uv run pytest src\aeat\application\filing src\aeat\application\workflow src\aeat\application\verification src\aeat\application\review src\aeat\domain\filing -q`
  passed: 297 tests.
- `uv run pytest src\aeat\application\workflow src\aeat\application\filing\test_schema_completeness.py src\aeat\application\review -q`
  passed: 149 tests after review fixes.
- `uv run ruff check src\aeat\application\filing src\aeat\application\workflow src\aeat\application\verification src\aeat\domain\filing`
  passed.
- `uv run ruff check src\aeat\application\workflow src\aeat\application\filing\test_schema_completeness.py src\aeat\application\review\test_aggregator.py src\aeat\application\review\test_adapters.py`
  passed.
- `uv run ty check src\aeat\application\filing src\aeat\application\workflow src\aeat\application\verification src\aeat\domain\filing`
  passed.
- `uv run ty check src\aeat\application\workflow src\aeat\application\filing\test_schema_completeness.py src\aeat\application\review`
  passed.
- `git diff --check` passed with existing CRLF normalization warnings only.
