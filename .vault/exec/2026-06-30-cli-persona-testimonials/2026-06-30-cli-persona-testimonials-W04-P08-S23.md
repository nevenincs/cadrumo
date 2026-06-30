---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S23'
related:
  - '[[2026-06-30-cli-persona-testimonials-plan]]'
---

# W04.P08.S23 Filed Observation Registry Enrollment Provenance

Scope: filed-data capture promotion into registry-grounded calculation observations.

## Description

RAG grounding:

- `uvx vaultspec-rag search "filed observation capture registry enrollment provenance live filed data CasillaObservation" --type code`
- `uvx vaultspec-rag search "filed observation provenance local filed observations non official evidence" --type vault --doc-type adr`

Single/source filed capture now fails closed when registry enrollment fails instead
of returning a successful capture report with missing calculation-history evidence.
Bulk capture records registry-enrollment failures as failure rows. Existing
provenance separation remains: local `app_filing` observations are non-official and
do not satisfy AEAT-official evidence gates.

## Outcome

Changed:

- `src/aeat/application/live/_filed_data_capture.py`
- `src/aeat/application/live/tests/test_filed_capture_calculation_history.py`

Review found no issues. The new regression exercises real persistence and
conversion paths without fake/mock/stub/monkeypatch shortcuts.

## Verification

Passed:

- `.venv\Scripts\python.exe -m pytest src/aeat/application/live/tests/test_filed_capture_calculation_history.py src/aeat/application/live/tests/test_filed_bulk_capture.py` -> 31 passed during worker and reviewer runs.
- W04 touched-file ruff gate in isolated latest-HEAD worktree passed.

Latest isolated retest note: current clean `HEAD` blocks registry-dependent filed
capture tests on baseline source byte-count mismatch `boe-modelo-210-base-order`.
The same retest also hit transient Windows resource exhaustion (`WinError 1450` /
`WinError 10055`) after parallel verification. These are not W04-owned changes.

