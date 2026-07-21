---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S16'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Reject Python lane evidence that lacks the installed tax and MCP oracles

## Scope

- `dev/packaging/tests/test_installed_oracles.py`
- `.github/workflows/packaging-smoke.yml`

## Description

- Run the installed tax oracle against the complete cohort.
- Run direct and meta-executed MCP tax work from the installed cohort.
- Retain source commit, artifact digests, direct origins, and child executable attestations.

## Outcome

- The installed-oracle gate rejects incomplete evidence and passed for the exact three-wheel cohort.
- The retained evidence binds both public transports and one identical supervised child executable hash.

## Notes

- Public-channel reacquisition remains open under S45 through S50.
