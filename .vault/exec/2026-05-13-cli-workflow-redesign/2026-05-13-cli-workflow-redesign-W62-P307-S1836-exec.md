---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W62.P307.S1836'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-registry-boundary-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-domain-harvest-normatives-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-unexposed-backend-capability-wave-expansion-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-s1836-code-review-audit]]"
---

# `cli-workflow-redesign` `W62.P307.S1836`

Removed tests that pinned rejected topic/help-root behavior while retaining tests for accepted registry corpus ownership and other retired command surfaces.

## Description

The CLI test suite no longer asserts `aeat app topic`, `_topic.py`, or topic-specific rejected-surface behavior. Registry corpus ownership remains guarded by tests that assert `citations` and `manuals` live only under `aeat app registry`, and other unrelated rejected command surfaces remain covered by their existing tests.

## Tests

Passed:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`
- `uv run --no-sync ty check src/aeat/entrypoints/cli/test_apex_workflow_verification.py src/aeat/entrypoints/cli/test_backend_boundary.py src/aeat/entrypoints/cli/test_cli_surface.py`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_apex_workflow_verification.py::test_rejected_aliases_do_not_reach_apex_workflow_services src/aeat/entrypoints/cli/test_backend_boundary.py::test_removed_workflow_shim_modules_stay_absent src/aeat/entrypoints/cli/test_cli_surface.py::test_app_help_lists_singular_domains src/aeat/entrypoints/cli/test_cli_surface.py::test_retired_invoice_declaration_and_archive_surfaces_are_not_user_facing -q`
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_registry_corpus.py::test_no_parallel_registry_corpus_surface_exists src/aeat/entrypoints/cli/test_registry_corpus.py::test_no_aeat_normatives_or_manual_fetch_verb_under_app_registry -q`

The focused touched-test slice passed with 4 tests. The registry corpus boundary slice passed with 2 tests. Code review returned no findings.
