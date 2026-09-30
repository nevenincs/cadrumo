---
tags:
  - '#exec'
  - '#docs-build-workflow'
date: '2026-09-29'
modified: '2026-09-30'
body_schema: 'body-v2'
body_hash: 'sha256:0f1707c742336746f044633e0a6bb47555084c3e30f7eb9d8b98b230b1ce75af'
related:
  - "[[2026-09-29-docs-build-workflow-plan]]"
---

# `docs-build-workflow` ledger

## Changes

- `S01` `A` `dev/docs/sequences/authority_currency.py`
- `S01` `M` `dev/docs/sequences/checks.py`
- `S01` `M` `dev/docs/sequences/cli.py`
- `S01` `A` `dev/docs/sequences/tests/test_authority_currency.py`
- `S01` `M` `dev/docs/sequence_build_gate.py`
- `S01` `M` `dev/docs/tests/test_sequence_build_gate.py`
- `S01` `verify:` `pytest dev/docs/sequences/tests -m '' (270 passed)` -> `pass`
- `S01` `verify:` `pytest dev/docs/tests/test_sequence_build_gate.py -m '' (11 passed)` -> `pass`
- `S01` `by:` `opus-medium`
- `S04` `D` `docs/api/*.rst (1,950 generated stubs)`
- `S04` `M` `.gitignore`
- `S04` `M` `docs/api/index.md`
- `S04` `M` `README.md`
- `S04` `M` `dev/docs/apidocs/manager.py`
- `S04` `M` `dev/docs/apidocs/__init__.py`
- `S04` `D` `dev/docs/apidocs/__main__.py`
- `S04` `D` `dev/docs/apidocs/cli.py`
- `S04` `D` `dev/docs/apidocs/tests/test_cli.py`
- `S04` `M` `dev/docs/apidocs/tests/test_manager.py`
- `S04` `M` `dev/docs/tests/test_api_stubs.py`
- `S04` `M` `dev/docs/tests/test_pruning_remedies_are_bounded.py`
- `S04` `M` `dev/tests/test_dev_cli_justfile_wiring.py`
- `S04` `M` `dev/registry/newmodelo/checklist.py`
- `S04` `M` `dev/quality/tests/test_suite_gate_table.py`
- `S04` `verify:` `pytest dev/docs/tests dev/docs/apidocs/tests dev/tests/test_dev_cli_justfile_wiring.py -m '' (448 passed, 1 pre-existing failure)` -> `pass`
- `S04` `by:` `opus-high`
- `S03` `M` `dev/docs/build.py`
- `S03` `M` `dev/docs/serve.py`
- `S03` `M` `docs/conf.py`
- `S03` `M` `justfile`
- `S03` `M` `dev/docs/tests/test_docs_build.py`
- `S03` `M` `dev/docs/tests/test_docs_serve.py`
- `S03` `verify:` `pytest dev/docs/tests/test_docs_build.py dev/docs/tests/test_docs_serve.py -m ''` -> `pass`
- `S03` `by:` `opus-high`
- `S02` `M` `dev/ci/change_scope.py`
- `S02` `A` `dev/ci/sequence_goldens_gate.py`
- `S02` `M` `.github/workflows/merge-gate.yml`
- `S02` `M` `.github/ci-control-plane.md`
- `S02` `M` `justfile`
- `S02` `M` `dev/ci/tests/test_change_scope.py`
- `S02` `A` `dev/ci/tests/test_sequence_goldens_gate.py`
- `S02` `M` `dev/ci/tests/test_ci_workflow.py`
- `S02` `M` `dev/docs/sequences/verdict_cache.py`
- `S02` `M` `dev/docs/sequences/tests/test_verdict_cache.py`
- `S02` `M` `dev/docs/sequence_build_gate.py`
- `S02` `M` `dev/quality/metadata/import_load_targets.json`
- `S02` `verify:` `pytest dev/ci/tests + justfile wiring + verdict and build-gate tests -m '' (751 parallel + 3 serial passed)` -> `pass`
- `S02` `verify:` `python -m dev.ci_contract .` -> `pass`
- `S02` `verify:` `python -m dev.actionlint` -> `pass`
- `S02` `by:` `opus-high`
- `S04` `M` `docs/authoring-guide.md`
- `S04` `M` `docs/reference/commands-and-configuration.md`
- `S04` `M` `docs/reference/registry-legal-api.md`
- `S04` `M` `docs/conf.py`
- `S04` `M` `docs/locales/{es,ca,hu}/LC_MESSAGES (9 catalogues)`
- `S04` `verify:` `pytest i18n, localization, user-scope and localized build tests -m '' (44 passed)` -> `pass`
- `S04` `by:` `opus-medium`
- `S05` `M` `dev/docs/sequences/verdict_cache.py`
- `S05` `M` `dev/docs/sequences/tests/test_verdict_cache.py`
- `S05` `M` `dev/ci/change_scope.py`
- `S05` `M` `dev/ci/tests/test_change_scope.py`
- `S05` `verify:` `pytest dev/docs/sequences/tests/test_verdict_cache.py dev/ci/tests/test_change_scope.py dev/ci/tests/test_sequence_goldens_gate.py` -> `pass`
- `S05` `verify:` `pytest dev/ci/tests dev/packaging/tests/test_verdict_cache_not_distributed.py` -> `pass`
- `S05` `verify:` `python -m dev.quality.import_gate` -> `pass`
- `S05` `verify:` `just docs-check` -> `pass`
- `S05` `verify:` `just docs-build` -> `pass`
- `S05` `verify:` `just docs-langs` -> `pass`
- `S05` `verify:` `just test-sequence-goldens-gate` -> `pass`
- `S05` `verify:` `python -m dev.docs.sequences check` -> `pass`

## Notes

- `S04` `test_docs_build_full_scope` failed before this change: autodoc mocked reportlab, so `summary_layout's` A4 unpack raised; reportlab removed from the mocks in the same commit
- `S03` Preview wall times: docs-page how-to/modelo-303 cold 29s, warm 22s; docs-page how-to (37 pages) 69s
- `S02` Cache-miss duration on the Linux fleet is projected at 6 to 6.5 minutes, not yet measured in CI
- `S05` Verdict key and documented-output change class now include the sequence engine's static dev-import closure (registry tooling excluded; its effect enters through the authority generation).
