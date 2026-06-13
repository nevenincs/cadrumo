---
tags:
  - "#audit"
  - "#live-write-test-audit"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-live-write-test-audit-research]]"
  - "[[2026-04-16-live-write-test-audit-reference]]"
  - "[[2026-04-16-live-write-test-audit-adr]]"
  - "[[2026-04-16-live-write-test-audit-plan]]"
---

# `live-write-test-audit`

Issue `#119` audit objective: verify that no pytest path in this repo can reach a live AEAT write.

## Procedure 1: research and audit execution

- Enumerated all matching test modules under `src/aeat/` and `tests/`.
- Audited the collected surface with `rg`, targeted file reads, and AST-backed checks to avoid false positives from comments and helper classes.
- Runtime collection check: `uv run pytest --collect-only` completed successfully and reported `927` collected tests, `24` deselected (`live`), and `903` selected by default.

## Procedure 2: marker integrity check

- Initial result: four tests in `tests/test_config.py` carried neither `unit` nor `live`.
- Remediation applied: added module-level `pytestmark = pytest.mark.unit` to `tests/test_config.py`.
- Post-fix result: zero marker-integrity failures across the full collected suite.

## Procedure 3: live-test write audit

- Audited every live-marked test body for:
  - `dry_run=False`
  - `submit(`
  - `live=True`
  - `--live`
  - `CONFIRMO`
  - `AEAT_LIVE_SUBMIT_ENABLED`
- Result: no live test body contains any forbidden token.
- AEAT-facing live-path observations:
  - `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` uses `SubmissionEngine.submit_draft(...)` on the dry-run path only.
  - `src/aeat/application/filing/test_live_complementaria.py` explicitly uses `dry_run=True`.
  - `src/aeat/application/workflow/test_live.py` does not submit anything.
  - `src/aeat/application/sync/test_live_sync.py` is read-only and currently dependency-gated.

## Procedure 4: fixture and conftest audit

- Repository `conftest.py` inventory: only `tests/conftest.py` exists.
- `tests/conftest.py` contains only a module docstring.
- No `conftest.py` autouse fixture sets `AEAT_LIVE_SUBMIT_ENABLED`.
- No test-side reference patches `aeat.adapters.outbound.aeat.export._confirm.request_human_submit_confirmation`.

## Procedure 5: import audit

- Submission-engine construction appears in:
  - `src/aeat/adapters/outbound/aeat/export/test_live_submission.py`
  - `src/aeat/adapters/outbound/aeat/export/test_engine.py`
  - `src/aeat/entrypoints/cli/submission/_helpers.py`
- Live-test result: the only live submission-engine construction remains on the dry-run path.
- Unit-test result: `src/aeat/adapters/outbound/aeat/export/test_engine.py` uses local doubles to simulate submitter/session behavior while asserting the live gate.

## Procedure 6: env var sanity

- `AEAT_LIVE_SUBMIT_ENABLED` is absent from the shell environment used for this audit.
- `AEAT_LIVE_SUBMIT_ENABLED` does not appear in `env/.env.example`.
- Canonical pytest live env surface documented by the repo:
  - `AEAT_LIVE_TESTS_ENABLED=false` by default
  - Scratch-resource IDs for Google live tests (`AEAT_SCRATCH_FOLDER_ID`, `AEAT_SCRATCH_SHEET_ID`, `AEAT_SCRATCH_DOC_ID`) are optional opt-in prerequisites
  - `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION=true` remains the submission-side safety gate

## Procedure 7: mock/patch audit

- No live-marked test body uses `monkeypatch`, `patch`, `Mock`, `MagicMock`, `AsyncMock`, or `mocker`.
- No live-marked test patches submission confirmation.
- Drift found in unit suites:
  - `src/aeat/adapters/outbound/aeat/export/test_engine.py` uses `_RecordingSubmitter`, `_Session`, `_OpenDeadlines`, and related doubles.
  - `src/aeat/application/workflow/test_engine.py` uses `_FakeSubmissionEngine` and multiple sibling `_Fake*` collaborators around the submission boundary.

## Findings

### Fixed in this execution

- `FIXED | marker-integrity | tests/test_config.py`
  - Four collected tests had no `unit` or `live` classification.
  - Fixed by adding module-level `pytestmark = pytest.mark.unit`.

### Not fixed here; escalated as gaps

- `OPEN | submission-boundary-doubles | src/aeat/adapters/outbound/aeat/export/test_engine.py`
  - The unit submission-engine suite relies on protocol doubles at the AEAT submission boundary instead of higher-fidelity real-behavior coverage.
  - Follow-up issue: `#150`.
- `OPEN | workflow-boundary-doubles | src/aeat/application/workflow/test_engine.py`
  - The workflow engine suite relies on `_FakeSubmissionEngine` and sibling doubles to model submission behavior, weakening end-to-end confidence around the hardened submission boundary.
  - Follow-up issue: `#151`.

## Final Verdict

- `GO`

The suite is currently safe against accidental live AEAT writes under pytest. The only direct suite-safety defect found in this audit was missing marker coverage in `tests/test_config.py`, and that defect has been fixed. Remaining concerns are quality gaps around submission-boundary doubles, not evidence of a reachable live AEAT write path.
