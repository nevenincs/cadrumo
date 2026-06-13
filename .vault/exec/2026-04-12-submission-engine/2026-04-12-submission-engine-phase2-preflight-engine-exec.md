---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: submission engine — phase-2 preflight + engine
related:
  - "[[2026-04-12-submission-engine-plan]]"
issue: wgergely/aeat#42
---

# phase-2: preflight + engine

## artefacts produced

- `src/aeat/adapters/outbound/aeat/export/_preflight.py` — four-gate `Preflight` validator
  (draft-ready, no-ERROR-findings, window-open, cert-loads) with INFO
  logging on every gate outcome.
- `src/aeat/adapters/outbound/aeat/export/_engine.py` — `SubmissionEngine.submit_draft`
  with dry-run default, double-gate for live mode, JSON persistence
  under `settings.aeat_submissions_dir`, and `load_submission` /
  `list_submissions` helpers.

## verification

- `uv run pytest src/aeat/adapters/outbound/aeat/export/test_preflight.py src/aeat/adapters/outbound/aeat/export/test_engine.py -q` — passed.
