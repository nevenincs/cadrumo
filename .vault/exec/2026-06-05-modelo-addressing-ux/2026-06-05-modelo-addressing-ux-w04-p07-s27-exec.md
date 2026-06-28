---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S27'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W04.P07.S27 resume ambiguity refusal and candidate guidance

Scope:
- `src/aeat/application/workflow/_resume.py`
- `src/aeat/application/workflow/__init__.py`
- `src/aeat/application/workflow/test_resume.py`
- `src/aeat/core/errors/registry/_application.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`
- `src/aeat/test_locale_coverage_hardened_errors.py`

## Description

- Added `WorkflowResumeRunCandidate` and `WorkflowResumeRunAmbiguousError` to the workflow resume boundary.
- Added `find_unique_run_for_period(modelo, period)` for natural-key resume flows that must refuse multiple matching persisted workflow runs instead of guessing.
- Preserved `find_latest_run_for_period(modelo, period)` for existing legacy work-unit-id compatibility while sharing the same run scan and newest-first ordering.
- Added `workflow_resume_candidate_lines(...)` candidate guidance with run id, modelo, period, final stage, aborted reason, and started timestamp.
- Exported the new workflow names through `aeat.application.workflow`.
- Registered the new AeatError subclass in the central error-code registry.
- Added localized workflow ambiguity messages in all supported locales and included the key in hardened locale coverage.

## Outcome

The workflow application layer now has a refusal shape and candidate projection for ambiguous natural-key resume. CLI implementation can use this without importing private workflow modules or inventing local ambiguity policy.

## Verification

- `uv run --no-sync ruff check src/aeat/application/workflow/_resume.py src/aeat/application/workflow/__init__.py src/aeat/application/workflow/test_resume.py src/aeat/core/errors/registry/_application.py src/aeat/test_locale_coverage_hardened_errors.py` passed.
- `uv run --no-sync pytest src/aeat/application/workflow/test_resume.py src/aeat/test_locale_coverage_hardened_errors.py src/aeat/core/i18n/test_placeholder_parity.py -q` passed with 98 tests.
- Public import smoke test for `WorkflowResumeRunAmbiguousError`, `WorkflowResumeRunCandidate`, `find_unique_run_for_period`, and `workflow_resume_candidate_lines` passed.
- YAML parse check for `en`, `es`, `ca`, and `hu` locale files passed.
