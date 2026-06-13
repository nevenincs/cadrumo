---
tags:
  - "#research"
  - "#live-write-test-audit"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-12-submission-engine-research]]"
  - "[[2026-04-16-live-write-test-audit-reference]]"
---

# `live-write-test-audit` research: `issue-119-suite-safety`

This research grounds issue `#119`, the test-suite safety audit for the AEAT live submission boundary. The scope is intentionally narrow: prove that no `pytest` path can reach a live AEAT write, land only narrow test-side fixes, and convert any broader boundary drift into follow-up issues rather than production edits.

## Findings

### Test surface and collection shape

- `uv run pytest --collect-only` succeeds on this branch and reports `927` collected tests, with `24` deselected by the default `-m 'not live'` filter and `903` selected.
- The suite spans `140` test modules under `src/aeat/` and `tests/`.
- There is exactly one repository `conftest.py`: `tests/conftest.py`, and it contains only a module docstring.

### Marker integrity

- The project declares only two local suite markers in `pyproject.toml`: `unit` and `live`.
- An AST walk across every collected test function found four marker-integrity failures before remediation, all in `tests/test_config.py`; those tests carried neither `unit` nor `live`.
- After adding a module-level `pytestmark = pytest.mark.unit` to `tests/test_config.py`, the same AST audit reports zero marker-integrity failures.

### Live-test write safety

- The actual bodies of every `@pytest.mark.live` test function were checked for `dry_run=False`, `submit(`, `live=True`, `--live`, `CONFIRMO`, and `AEAT_LIVE_SUBMIT_ENABLED`.
- No live test body contains any of those tokens.
- The only live AEAT submission-path tests found are dry-run or read-only:
  - `src/aeat/adapters/outbound/aeat/export/test_live_submission.py`
  - `src/aeat/application/filing/test_live_complementaria.py`
  - `src/aeat/application/workflow/test_live.py`
  - `src/aeat/application/sync/test_live_sync.py`

### Fixture and environment surface

- No `conftest.py` autouse fixture sets `AEAT_LIVE_SUBMIT_ENABLED`.
- No test fixture or helper monkeypatches `aeat.adapters.outbound.aeat.export._confirm.request_human_submit_confirmation`; the symbol is not referenced anywhere in the repo.
- `AEAT_LIVE_SUBMIT_ENABLED` is not defined in `env/.env.example`, not referenced in test code, and was not present in the shell environment during the audit.
- The canonical live-test gate in this repo is `AEAT_LIVE_TESTS_ENABLED=false` in `env/.env.example`.

### Submission-engine import and double usage

- `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` constructs a real `SubmissionEngine` and exercises only `engine.submit_draft(_Draft())`, which stays on the dry-run path.
- `src/aeat/application/filing/test_live_complementaria.py` uses `build_engine(...)` and explicitly calls `engine.submit_amendment(..., dry_run=True)`.
- Separate from live-write safety, the unit suites under `src/aeat/adapters/outbound/aeat/export/test_engine.py` and `src/aeat/application/workflow/test_engine.py` rely on `_RecordingSubmitter`, `_Session`, and `_FakeSubmissionEngine` style doubles around the submission boundary. These do not expose a live AEAT write path, but they do drift from the repo’s no-fakes test charter and require follow-up work beyond a narrow marker fix.

## Outcome

- The suite currently appears safe against accidental live AEAT writes under `pytest`.
- One narrow test-side defect existed and was fixed locally: missing `unit` markers in `tests/test_config.py`.
- The remaining meaningful drift is architectural test-quality debt around submission/workflow doubles, which should be tracked as follow-up issues rather than patched opportunistically in this audit.
