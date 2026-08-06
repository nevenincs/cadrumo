---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:3461668572cc3fa30238301a10790cf61e927616882c50be2333b0e638025659'
step_id: 'S13'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit df75c1b63) - category 3 golden scenario dispatching a real modelo.work.calculate call and asserting legal_refs/source_refs on the response payload, not only the registry

## Scope

- `src/aeat/agent/eval/tests/test_response_provenance_golden.py`

## Description

- Author the category-3 golden scenario dispatching a real
  `modelo.work.calculate` call through the harness.
- Assert `legal_refs`/`source_refs` provenance is carried on the
  response payload itself, not only recoverable from the registry, per
  `aeat-calculation-grounding`.
- Add the anti-tautology proof dispatched against the real CLI.

## Outcome

Landed in commit `df75c1b63` alongside the other six category golden
scenarios (cat-1/3/4/5/7/8/9). 50 eval tests green at landing.

## Notes

None.
