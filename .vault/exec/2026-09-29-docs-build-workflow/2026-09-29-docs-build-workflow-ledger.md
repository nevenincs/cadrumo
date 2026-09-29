---
tags:
  - '#exec'
  - '#docs-build-workflow'
date: '2026-09-29'
modified: '2026-09-29'
body_schema: 'body-v2'
body_hash: 'sha256:712bd97cfcb8096fc52707690bd3fc76aff533b5c604be04a17deb1c310762df'
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

## Notes

- `S04` `test_docs_build_full_scope` failed before this change: autodoc mocked reportlab, so `summary_layout's` A4 unpack raised; reportlab removed from the mocks in the same commit
- `S03` Preview wall times: docs-page how-to/modelo-303 cold 29s, warm 22s; docs-page how-to (37 pages) 69s
