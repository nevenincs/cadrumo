---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S86'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S86 Core Domain Error Registry Verification

Scope: verify core domain error registry behavior and facade imports after decomposition.

## Description

- Ran Ruff over the core error registry, core error tests, and core boundary contract.
- Ran the focused core error registry and boundary test lane.
- Smoke-tested registry aggregation and public `aeat.core.errors` lookup for a domain error class.

## Outcome

The split registry shards preserve behavior, registry enforcement, and core boundary rules.

## Notes

Focused verification passed with 39 core error, boundary, and settings-surface tests, plus direct before/after registry equality and public lookup smoke checks. The broad `src/aeat/core/tests` lane failed on unrelated stale meta-test path assumptions and one external-constant alias assertion; that residual is tracked as W04.P09.S152.
