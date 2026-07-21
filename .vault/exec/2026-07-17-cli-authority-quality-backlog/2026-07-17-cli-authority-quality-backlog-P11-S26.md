---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S26'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Add a structural no-build/no-publish assertion to the publish-workflow guardrail test: denylist-scan every step run and uses in the validate job (or pin the full step allowlist) so a differently-spelled build or publish command cannot slip past the exact-substring guards, gated on the guardrail test failing if any validate-job step invokes a build or publish tool

## Scope

- `dev/release/tests/test_publish_workflow.py`

## Description

- Add a whitespace-tolerant regex denylist of build/publish tool invocations
  (`uv build`/`uv publish`, `python -m build`/`-m twine`, `twine upload`,
  `pip wheel`, `poetry`/`flit`/`hatch`/`pdm build`/`publish`, `setup.py` build/upload,
  `gh release create`/`upload`) plus publish-capable `uses` markers.
- Add a pure scanner `_build_publish_invocations(step)` over a step's `run` and `uses`.
- Add a gate test that parses the real `publish.yml`, scans every validate-job step,
  and fails if any invokes a build or publish tool.
- Add a non-vacuity test proving the scanner catches differently-spelled variants
  and leaves the workflow's real benign steps unflagged.

## Outcome

The publish-workflow guardrail no longer relies solely on exact-substring
`"uv build" not in workflow_text` checks. The new structural gate parses
`publish.yml`, iterates the single `validate` job's step table, and denylist-scans
each step's `run` and `uses` through whitespace-tolerant regexes, so a
differently-spelled build or publish command — a double-spaced `uv  build`, a tabbed
`uv\tpublish`, `python -m build`, `python3.11 -m build`, `twine upload`,
`poetry publish`, `hatch build`, `python setup.py sdist bdist_wheel`, or
`gh release create` — is caught where the old substring guards would miss it. The
`uses` scan denies `gh-action-pypi-publish`, `pypi-publish`, and `action-gh-release`.

The non-vacuity is proven by a companion test that feeds the scanner thirteen
forbidden variants (each asserted flagged) and five real benign shapes — including
`actions/checkout`, `astral-sh/setup-uv`, `gh run download`,
`uv run --frozen python -m dev.release.promote_python_cohort --check-pypi`, and the
"Publication remains blocked ... GitHub release ..." echo — each asserted unflagged,
confirming the scanner distinguishes a build/publish invocation from the workflow's
legitimate read-only diagnostic steps. The gate test scans real `publish.yml` bytes
(no mock/monkeypatch/skip/xfail); the real workflow reports zero invocations. All four
tests in the module pass; Ruff check/format and the `ty` type check are clean.

## Notes

Test-only change scoped to one file; no production surface touched and no publication
capability added. The scanner is intentionally more permissive than the exact command
grammar (it flags a build/publish token pair regardless of spacing), which is the
correct bias for a fail-closed guardrail: a false alarm forces a reviewer to justify a
new validate-job command, while a missed build/publish invocation would defeat the
guard.
