---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S42'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W05.P13.S42`

## Scope

Test documentation.

## Description

- Verified `src/aeat/tests/README.md` documents the tests-folder topology, `test_*.py` naming rule, execution markers, hexagonal markers, live-read opt-in, banned imports, plugin roster, and new-test checklist.
- Replaced retired docs-tool pytest markers with the active `unit` plus `hex_core` or `hex_entrypoint` vocabulary.
- Removed stale docs-marker lane prose from docs tooling tests.
- Ran marker integrity, docs-tool marker scan, focused docs-build tests, docs API collection, and ruff over the touched docs-tool tests.

## Outcome

The central test README matches `pyproject.toml`, `src/aeat/tests/test_marker_integrity.py`, and `src/aeat/tests/conftest.py`. No retired marker usage remains in docs tooling tests. Marker integrity passed 2070 checks; docs build hygiene passed 7 selected checks with the long Sphinx build deselected; docs API tests collected 8 items; ruff selected checks passed.

## Notes

The full `docs/tools/tests/test_docs_build.py` run still fails in `test_sphinx_nitpicky_build_is_clean` because of broader concurrent docs/source warnings: `_styling.py` docstring formatting, missing `modelo-303` Sphinx references under the current dirty docs tree, two unresolved API references, and an unlinked `USERDOCS-KICKOFF-BRIEF.md`. Those warnings are not hidden by this record. No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
