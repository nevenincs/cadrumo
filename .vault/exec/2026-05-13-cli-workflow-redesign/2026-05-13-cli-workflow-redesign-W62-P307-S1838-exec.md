---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P307.S1838'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-s1838-code-review-audit]]"
---

# `cli-workflow-redesign` `W62.P307.S1838`

Updated the backend boundary inventory so registry-corpus command ownership is recorded in `test_backend_boundary.py`.

## Description

The boundary inventory now asserts that `citations` and `manuals` Typer applications are owned only by the canonical `_registry_corpus.py` module under `aeat app registry`. The duplicated ownership guard was removed from the registry-corpus behavior test file so corpus tests stay focused on command behavior while the inventory owns structural boundary checks.

The update intentionally does not reintroduce tests for rejected topic/help-root command paths; S1836 removed those assertions from the CLI test corpus.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_registry_corpus.py`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_registry_corpus.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py::test_registry_corpus_cli_ownership_is_registry_only src/aeat/entrypoints/cli/test_registry_corpus.py::test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_registry_corpus.py src/aeat/application/topics/test_catalogue.py -q`

The focused ownership slice passed with 2 tests. The broader W62 boundary slice passed with 27 tests. Code review returned no findings.
