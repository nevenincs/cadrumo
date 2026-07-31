---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-19'
modified: '2026-07-19'
body_hash: 'sha256:347b82b199c7466cac8bc9043b7e645a5457a2729accc6aaaedb9961ebf0bd22'
step_id: 'S04'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

# RESOLVED by accepted ADR 2026-07-18-mcpb-signing-publisher-adr, the MCPB ships unsigned by operator decision (no purchased certificate), integrity channel is the published SHA-256 plus in-bundle cohort digest pins already enforced by the bootstrap, no signing identity to bind

## Scope

- `packaging/mcpb/build.py`

## Description

- Resolve the MCPB signing-identity requirement through the accepted `2026-07-18-mcpb-signing-publisher-adr`: the MCPB ships unsigned by operator decision (no purchased certificate).
- Record the integrity channel that replaces a signing identity: the published SHA-256 plus the in-bundle cohort digest pins the bootstrap already enforces.

## Outcome

The step's acceptance criterion (an MCPB signing identity binding to the immutable cohort) is met by the operator's accepted decision that there is no signing identity to bind; integrity rides the published SHA-256 and the bootstrap-enforced cohort digest pins in `packaging/mcpb/build.py`. Closed against an accepted resolving ADR, not against a CI run.

## Notes

Retroactive execution record reconstructed from the step row and the accepted ADR; the step was already checked. No new work; vault-only bookkeeping.
