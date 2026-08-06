---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:f2f79ff08a680d91b9788915d2d690399dace64a59a5ddc3867f7abc2448daec'
step_id: 'S03'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit 6e7fc1629) - split Category A behavioural-invariant rules and extract manifest-derived operator-orientation-routing (Category B)

## Scope

- `src/aeat/_data/agent/rules/`

## Description

- Keep the theme-clustered behavioural-invariant operator rule files
  (Category A) as-is per D4's Option 3 hybrid.
- Extract orientation/routing content into one new manifest-derived
  `operator-orientation-routing` rule (Category B), alongside the existing
  stable `operator-envelope-reading` rule.

## Outcome

Landed in commit `6e7fc1629`. Net effect matches the ADR's stated ~4 -> ~7
file restructure across Categories A/B/C.

## Notes

None.
