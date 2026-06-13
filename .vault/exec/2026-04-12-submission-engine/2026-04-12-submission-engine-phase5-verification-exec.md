---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: submission engine — phase-5 verification gates
related:
  - "[[2026-04-12-submission-engine-plan]]"
issue: wgergely/aeat#42
---

# phase-5: live test + verification gates

## artefacts produced

- `src/aeat/adapters/outbound/aeat/export/test_live_submission.py` — one
  `@pytest.mark.live` test gated on `AEAT_LIVE_TESTS=1`, performs a
  dry-run only (the `_NoopSubmitter.submit` method asserts it is
  never called).

## verification gates

| Gate                                          | Status |
| :-------------------------------------------- | :----- |
| `uv run pytest src/aeat/submission -q`        | PASS   |
| `uv run pytest src/aeat/entrypoints/cli/submission -q`    | PASS   |
| `uv run pytest tests/test_config.py -q`       | PASS   |
| `just lint`                                   | PASS   |
| `just typecheck`                              | PASS   |
| `just test`                                   | PASS (362 passed, 1 skipped, 10 deselected) |
| `just hooks`                                  | PASS   |
