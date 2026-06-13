---
tags:
  - "#exec"
  - "#pytest-markers"
date: 2026-04-17
modified: '2026-04-17'
related:
  - "[[2026-04-17-pytest-markers-plan]]"
  - "[[2026-04-17-pytest-markers-adr]]"
---

# pytest-markers phase-3 step-2

## migrate-domain-submission-test-modules

Applied module-level `pytestmark = [pytest.mark.<access>, pytest.mark.domain_submission]` to the 11 modules in the inventory. Every previously `live`-marked file in the submission domain became `live_read` (zero became `live_write`). `src/aeat/adapters/outbound/aeat/export/_engine.py` (host of the R5 runtime refusal) is byte-identical.

## verification

- `uv run pytest src/aeat/filing src/aeat/submission -m unit` -> green.
- `uv run pytest --collect-only src/aeat/adapters/outbound/aeat/export/test_live_submission.py -m live_write -q` -> 0 items.
- `git diff src/aeat/adapters/outbound/aeat/export/_engine.py` -> empty.
