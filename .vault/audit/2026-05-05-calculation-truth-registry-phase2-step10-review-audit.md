---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-05-calculation-truth-registry-phase2-step10-exec]]'
---



# `calculation-truth-registry` Code Review

PHASE2-STEP10-001 | MEDIUM | Workflow draft schema guard accepted fabricated same-model registry revisions

`_engine.py` required only a `registry:{modelo}:` schema namespace. A draft
with `registry:130:unregistered` could pass the workflow guard. Resolved by
loading the active registry schema for the resolved obligation period and
requiring an exact `schema_version` match before draft validation or preflight.
`test_engine.py` now covers both wrong-model namespace and same-model inactive
revision failures.

PHASE2-STEP10-002 | MEDIUM | Filing schema projection test did not prove registry formula projection

`test_schema_completeness.py` selected casillas with projected
`formula_inputs` and then proved those projected inputs resolved. Resolved by
deriving formula-bound casillas and expected casilla references from the
registry snapshot expression graph, then comparing the runtime provider
projection against those expected references.

PHASE2-STEP10-003 | LOW | Review and workflow tests carried hardcoded registry revision strings

The old fallback string was removed, but some tests replaced it with a
literal `registry:130:...` value. Resolved by deriving the active schema
version through `build_runtime_schema_provider`.

PHASE2-STEP10-004 | LOW | Step record validation scope was incomplete

The step record listed review-test edits but the recorded static-check command
omitted those touched tests. Resolved by updating the step record with the
review test files and scoped `ruff` command that includes them.
