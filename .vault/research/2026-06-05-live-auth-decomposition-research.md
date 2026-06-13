---
tags:
  - '#research'
  - '#live-auth-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - "[[2026-06-04-repo-health-triage-research]]"
  - "[[2026-06-04-repo-health-triage-live-auth-split-invariants-audit]]"
  - "[[2026-06-04-live-auth-decomposition-adr]]"
---

# `live-auth-decomposition` research: `Live auth decomposition research bridge`

## Scope

This bridge records the evidence chain behind the live-auth decomposition ADR.
It does not reopen implementation scope. It connects the repo-health complexity
triage to the dedicated live/auth invariant audit so future agents brief from
the custody-boundary decision rather than from scattered auth, browser, live,
and CLI surfaces.

## Findings

- **R01:** The live/auth split is authorized because the repo-health triage
  identified live/auth as a complexity hotspot, not because a new auth product
  or provider is being introduced.
- **R02:** The invariant audit establishes the required custody boundaries:
  application auth owns session acquisition and identity alignment, provider
  adapters own provider mechanics, the browser adapter owns Playwright context
  construction, application live owns live-read orchestration, and CLI remains
  rendering-only.
- **R03:** Decomposition must preserve read-only live access, encrypted session
  state, redacted diagnostics, and fail-closed profile/provider identity checks.
