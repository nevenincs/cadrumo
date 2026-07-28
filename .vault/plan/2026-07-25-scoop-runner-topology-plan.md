---
tags:
  - '#plan'
  - '#scoop-runner-topology'
date: '2026-07-25'
modified: '2026-07-28'
tier: L1
related:
  - '[[2026-07-22-scoop-runner-topology-adr]]'
  - '[[2026-07-17-post-release-distribution-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `scoop-runner-topology` plan

- [ ] `S01` - Switch the self-hosted Windows host running docker into WINDOWS-container mode, since the packaging-scoop preflight correctly refuses on server os linux and the workflow header states the preflight must not be weakened, OPERATOR-GATED as a host action; `operator action, self-hosted Windows host docker daemon`.
- [ ] `S02` - Re-run the clean Scoop acquisition gate on the declared Windows release row, since the latest run 29895961436 refused at the docker-mode preflight and no clean acquisition evidence exists; `.github/workflows/packaging-scoop.yml`.
- [ ] `S03` - Enable Windows Sandbox on the Windows host so the install-from-bucket smoke can execute CLI, MCP, update, and persistence behaviour, OPERATOR-GATED as a host action; `operator action, Windows host feature`.
- [x] `S04` - Record an explicit unaffected-and-why reconciliation against the account-distribution-standard ruling, because this record governs which runner executes the Scoop evidence lane while that record governs where Scoop manifests live, and a reader finding two Scoop decisions with no stated relationship must not have to re-derive the orthogonality; `.vault/adr/2026-07-22-scoop-runner-topology-adr.md`.
## Description

## Steps

## Parallelization

## Verification

## Context

Accepted ADR carrying no plan. Rules which runner executes the Scoop evidence lane; orthogonal to where Scoop manifests live, which the account-distribution-standard ADR settles. The packaging-scoop preflight correctly refuses on docker server os linux and must not be weakened.
