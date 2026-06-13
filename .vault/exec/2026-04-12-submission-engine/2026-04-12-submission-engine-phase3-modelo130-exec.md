---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: submission engine — phase-3 modelo130 submitter
related:
  - "[[2026-04-12-submission-engine-plan]]"
issue: wgergely/aeat#42
---

# phase-3: submitter ABC + modelo130

## artefacts produced

- `src/aeat/adapters/outbound/aeat/export/_submitters/__init__.py` — `Submitter` ABC
  exposing `dry_run` / `submit` coroutines.
- `src/aeat/adapters/outbound/aeat/export/_submitters/_contract.py` — narrow
  `BrowserSessionLike` Protocol.
- `src/aeat/adapters/outbound/aeat/export/_submitters/modelo130.py` — `Modelo130Submitter`
  walking the portal with screenshots, trace start/stop, and a
  pre-submit abort in dry-run mode.
- `src/aeat/adapters/outbound/aeat/export/_submitters/test_modelo130.py` — unit tests
  using a `RecordingSession` Protocol implementation (no mocks).

## verification

- `uv run pytest src/aeat/adapters/outbound/aeat/export/_submitters -q` — passed.
