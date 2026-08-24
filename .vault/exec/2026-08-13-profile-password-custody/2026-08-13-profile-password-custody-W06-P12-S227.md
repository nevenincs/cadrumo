---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c685974ae08b1d202c6b796ad1da4e3b4dd1630236cbe3190a6ec5867278d276'
step_id: 'S227'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Retire the unsupported workstation agent-materialisation sequence and stale agent-extra claims while preserving the separately owned harness and MCP guidance

## Scope

- `docs/workstation-setup.md and docs/_sequences/contracts/workstation-setup/`

## Description

- Reconcile concurrent commit `1beef77048` against the live CLI command tree and separate `cadrumo-harness` workspace-package authority.
- Confirm the unsupported workstation agent-materialization sequence and `aeat app agent --output` claim are absent.
- Confirm workstation MCP guidance retains the legitimate `uv sync --package cadrumo-harness` and `uv run --package cadrumo-harness cadrumo-mcp --help` source-checkout workflow.
- Run documented-command conformance, sequence contract/build coherence, the target live page check, the user-scope nitpicky build, and independent review.

## Outcome

Concurrent commit `1beef77048` deleted the unsupported `install-agent-harness` sequence and removed its workstation page directive while preserving the separately owned MCP and harness guidance. Independent review found its orphan golden still recorded `aeat app agent --output` as a successful command, so this Step deleted that stale generated record. Current documentation and sequence evidence now match the live absence of an `aeat app agent` CLI verb and the workspace's separate `cadrumo-harness` package.

The final complete documented-command conformance module passed all 349 tests in 4.73 seconds. The final sequence contract, build-gate, and golden-crash focus passed 10 tests in 1.42 seconds. A targeted source search found no remaining `install-agent-harness`, `app agent`, or `--output ./operator-workspace` claim across the workstation page and sequence corpus. The target workstation sequence check and the user-scope nitpicky build both stopped before evaluating this page because whole-registry validation currently rejects Modelo 303 revision 2023 and Modelo 322 revision 2008-2022 while `deadline_windows` remain pending under filing-grade authority.

## Notes

The production harness package still contains docstrings and a missing-SDK install hint that name the retired `cadrumo[agent]` extra. Formal review classified those source strings as a LOW follow-on outside S227's declared workstation documentation and sequence paths; they remain explicit rather than being mistaken for a workstation-doc pass. The external registry blocker is likewise recorded rather than represented as green and belongs to the registry authority campaign.
