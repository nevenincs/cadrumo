---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:9fb0a92d76b0401dfb8c1ea357f2597e4c02f0178b6a90b2239e29a62d4d016d'
step_id: 'S92'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Exercise the production supervisor and executors against deterministic local HTTP and browser fixtures with real async resources and trace logging

## Scope

- `src/cadrumo/application/operations/tests/test_real_resource_lifecycle.py`

## Changes

- `A` `src/cadrumo/application/operations/tests/test_real_resource_lifecycle.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_real_resource_lifecycle.py -m integration -n0 -q` -> `pass`

## Notes

Discovery for this Step ran against the local fallback search index, not the live
semantic-search service, which was down for the session. Absence of a result in that
index is therefore not evidence that no such code exists; every claim about what does
or does not exist in the tree was confirmed by direct search of the source rather than
by the index alone.

The operation definition and executor exercised here are declared by the test. The
supervisor, the executor context, the browser adapter and all three persistence
adapters are the production objects, and the resource release proven is the
supervisor's own: neutering its cleanup method leaves a real Chromium and a real
Playwright runtime open, which is what establishes that. No shipped definition
declares the owned-process capability this Step requires, so the proof covers the
supervisor honouring the contract and not any shipped operation exercising it.

The absence claim about sensitive data carries two positive controls, because an
absence proof without them is satisfied by scanning nothing: the executor is shown to
genuinely hold the sensitive value, and the byte scan is shown to genuinely read the
durable content.
