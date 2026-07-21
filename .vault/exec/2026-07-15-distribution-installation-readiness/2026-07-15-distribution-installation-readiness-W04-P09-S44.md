---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S44'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Prove the publish workflow cannot build regenerate or accept unrelated artifacts

## Scope

- `dev/release/tests/test_publish_workflow.py`

## Description

- Parse the real `publish.yml` workflow document and assert it exposes a single
  `validate` job whose only dispatch input is `packaging_run_id`.
- Assert the workflow permissions are read-only (`actions: read`, `contents: read`)
  with no `id-token: write`, so no OIDC publish identity is available.
- Assert the validation surface binds to the `packaging-smoke.yml` authority run,
  refuses any run whose conclusion is not `success`, downloads only the two named
  cohort and evidence artifacts, and pins `actions/checkout` to that run's source
  commit rather than an arbitrary ref.
- Assert the workflow and `justfile` carry no build, publish, or upload capability:
  no `uv build`, no `uv publish`, no PyPI environment, and no `UV_PUBLISH_TOKEN`.
- Assert the retained-byte diagnostic keeps publication explicitly blocked with its
  standing "Publication remains blocked" notice.

## Outcome

The guardrail proof runs as real-behaviour coverage against the shipped
`publish.yml` and `justfile`; no mock, monkeypatch, skip, or xfail is used. Both
tests pass (`2 passed`), and focused collection is clean.

The workflow is proven fail-closed. It accepts exactly one caller-supplied
`packaging_run_id`, resolves that run through the GitHub API, and refuses to proceed
unless the run both concluded `success` and originated from the
`.github/workflows/packaging-smoke.yml` authority workflow. It then downloads only
the `cadrumo-python-cohort` and `cadrumo-packaging-smoke-evidence` artifacts of that
one run and checks out exactly that run's `source_commit`, so an unrelated or
attacker-chosen artifact set cannot enter the validation. The workflow runs
`dev.release.promote_python_cohort --check-pypi` as a read-only hash and
completeness diagnostic and carries no build, regeneration, or upload command: it
contains no `uv build`, no `uv publish`, no `id-token: write`, no `pypi` environment,
and no `UV_PUBLISH_TOKEN`, and the `justfile` retains no publish token or
`publish confirm` upload recipe. Publication therefore stays structurally impossible
from this workflow, which is consistent with the operator-held publish decision.

## Notes

This step is a structural guardrail proof only; it neither publishes nor enables any
publication path, and the operator publish hold is untouched. The verification
exercises the real workflow and justfile bytes, so any future edit that reintroduces
a build, upload, OIDC-write, or unrelated-artifact acceptance path reddens this gate.
