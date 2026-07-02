---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S05'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit 6e7fc1629) - add the negative conformance gate sourcing its internal-name blocklist from the manifest's own service_owner values

## Scope

- `src/aeat/agent/tests/test_rule_surface_conformance.py`

## Description

- Add a negative conformance assertion forbidding an operator rule from
  naming an internal (`aeat.<pkg>...`, a `src/aeat/...` path, a private
  `_module`, a `test_*` name).
- Source the blocklist from the manifest's own `service_owner` string
  values rather than a hand-written regex, so a new backend module cannot
  leak into rule prose by omission and legitimate CLI-domain nouns are
  never false-positived.

## Outcome

Landed in commit `6e7fc1629`. The empirical false-positive check the ADR's
Constraints section required (no `service_owner` value coincides with an
operator-facing noun) passed.

## Notes

None.
