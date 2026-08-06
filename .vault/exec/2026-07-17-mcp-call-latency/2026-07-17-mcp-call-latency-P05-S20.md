---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:87fdedc3fec4085982759f9d1227ebe4d14e6a4162d0d36ca8e4f40b66deffd5'
step_id: 'S20'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

# Rebuild the release cohort so the v0.2.1 train re-runs installed-behavior evidence against the new caches and warm serving

## Scope

- `dev/packaging/release_cohort.py`

## Description

- Rebuild the release cohort from the fully-fixed HEAD so the v0.2.1 train
  re-runs installed-behavior evidence against the new caches and warm serving.

## Outcome

- New immutable cohort id
  `a027ea57c148727869bb92354b7961b84c24177c3a0afdadf8e7321b8a84c4c3`,
  version 0.2.1, source commit `df344ddbd782b2f36abef1f65c79e1b350ad5d8d`,
  all twelve members digest-bound. This cohort carries every campaign change:
  the event-loop fix, validation-verdict cache with wheel-stamped verdict,
  shipped corpus text, hardened compiled-registry cache, warm in-process MCP
  serving with wedge fallback, the self-healing MCPB bootstrap, the
  destructive-reset risk declarations, and the digest-fragment install
  enforcement.

## Notes

- This cohort supersedes `616f48fc…` (commit `044e48450e`); the
  distribution-installation-readiness evidence matrix rows (S34 onward) should
  bind to this or a later cohort, not the superseded one.
