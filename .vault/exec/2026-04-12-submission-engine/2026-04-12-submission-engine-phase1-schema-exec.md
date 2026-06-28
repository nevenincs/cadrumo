---
tags:
  - "#exec"
  - "#submission-engine"
date: 2026-04-12
modified: '2026-04-12'
title: submission engine — phase-1 schema
related:
  - "[[2026-04-12-submission-engine-plan]]"
  - "[[2026-04-12-submission-engine-adr]]"
issue: wgergely/aeat#42
---

# phase-1: schema + errors + protocols

## artefacts produced

- `src/aeat/adapters/outbound/aeat/export/_errors.py` — `SubmissionError` hierarchy with
  `Translatable` payloads.
- `src/aeat/adapters/outbound/aeat/export/_protocols.py` — Protocol + pydantic stubs for
  #6 / #7 / #8 / #23 / #38 / #39 / #44.
- `src/aeat/adapters/outbound/aeat/export/_models.py` — `SubmissionStatus`,
  `SubmissionAttempt`, `SubmittedFiling`, `make_submission_id`
  (strict+frozen pydantic v2, model-validator invariants for time
  ordering and `ACKNOWLEDGED` state consistency).

## verification

- `uv run pytest src/aeat/adapters/outbound/aeat/export/test_models.py src/aeat/adapters/outbound/aeat/export/test_errors.py -q` — passed.
