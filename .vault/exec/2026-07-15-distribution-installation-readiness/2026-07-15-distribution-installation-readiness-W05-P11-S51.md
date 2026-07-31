---
tags:
  - '#exec'
  - '#distribution-installation-readiness'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:df5d3fb41a4e62d412cfedebc0c22dcc977a37ba24d3e0c9f0da4a0de2b6299e'
step_id: 'S51'
related:
  - "[[2026-07-15-distribution-installation-readiness-plan]]"
---

# Define the installation guide information architecture and evidence-backed claim boundaries

## Scope

- `.vault/reference/2026-07-15-distribution-installation-readiness-reference.md`

## Description

- Define the installation-guide information architecture across the four
  user-facing surfaces and bind every acquisition claim to evidence.
- Append the architecture section to the feature reference document.

## Outcome

- The reference document now defines: README as the shortest proven path per
  audience; `docs/workstation-setup.md` owning Python/Scoop/Homebrew install,
  verify, update, and removal; `docs/how-to/connect-an-agent.md` owning the
  Claude Code, Claude Desktop, and Cowork plugin plus MCPB paths with real
  verification commands; and `docs/updates.md` publishing the measured support
  matrix with unexecuted rows labelled unsupported.
- Claim boundaries are declared machine-enforced: the channel-pattern-to-row
  mapping gate authored under S56 fails any page advertising a channel without
  matching acquisition evidence, documented commands must resolve through the
  command-conformance gate, and the W05 writing order is matrix first, channel
  sections second, README last, so documentation trails evidence by
  construction.

## Notes

- Authored by the plan owner directly (principal documentation authorship).
  The section deliberately makes no availability claim; S52-S55 remain gated
  on public reacquisition evidence per the plan's parallelization contract.
