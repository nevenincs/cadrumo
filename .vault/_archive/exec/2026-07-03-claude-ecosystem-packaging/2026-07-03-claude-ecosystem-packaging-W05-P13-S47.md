---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:4f5b9980dfe5d212952061f33a50563a43076c12619ec8ca46125990ca14b3df'
step_id: 'S47'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Record the verified support matrix (which clients run the local server vs skills-only) that the userdocs will state

## Scope

- `docs/verification/support-matrix.md`

## Description

- Author `docs/verification/support-matrix.md`: the measured — never aspirational — per-client capability matrix (marketplace install, runtime resolution, configure surface, local server spawn, full tool round-trip, permission gate) across Claude Code CLI, Claude Desktop, and Cowork, each row backed by the sibling install-proof documents.
- Record the launch-variant note (local wheel now, PyPI variant re-verify after first publish) and the explicit out-of-scope claims (claude.ai web not measured; the S46 golden itinerary is the remaining scenario measurement).
- Commit `d0694a9e66`.

## Outcome

- The userdocs have a single measured source of truth for what may be claimed per client.

## Notes

Executed inline by the coordinator. S46 (golden regularizar-atrasos itinerary through the installed plugin) remains the one open step and is tracked operator-gated together with the first publish.
