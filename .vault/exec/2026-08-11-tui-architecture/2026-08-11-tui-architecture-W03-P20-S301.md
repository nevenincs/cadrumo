---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:6f25db0be0cc69e7dd4ad115e9f0b61644d2350be6e4b6ca55229563ed48ddeb'
step_id: 'S301'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Lock the typed materialization-provenance error to its own gate: the facet now raises a named subclass instead of a bare ValueError, but the only assertion anywhere matches the base class and its message, so a regression back to a bare raise with the same text passes green and the typed error is defended by nothing; assert the named class in the gate that already exercises the path

## Scope

- `src/cadrumo/application/modelo/tests/test_workspace.py materialization-provenance refusal assertion`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_workspace.py` -- `test_graded_snapshot_materialization_facet_refuses_a_row_value_with_no_provenance` now asserts `ModeloWorkspaceMaterializationProvenanceMissingError` (imported from `..workspace`) instead of the base `ValueError`
- `verify:` gate proven unproven-until-it-bites via an outside-the-repo runtime monkeypatch (no tracked file touched): wrapped `graded_snapshot_materialization_facet` to catch the real named error and re-raise a bare `ValueError` with the same message, confirmed the updated test REDS against that simulated regression, then confirmed it passes again against the real, unpatched code
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -q -m integration -n 0 -k "refuses_a_row_value_with_no_provenance"` -> `pass` (1 passed)
