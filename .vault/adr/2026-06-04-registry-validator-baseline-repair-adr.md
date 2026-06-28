---
tags:
  - '#adr'
  - '#registry-validator-baseline-repair'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - "[[2026-06-04-registry-validator-baseline-repair-plan]]"
  - "[[2026-06-04-registry-validator-baseline-repair-research]]"
---


# `registry-validator-baseline-repair` adr: `phase two authority alignment` | (**status:** `accepted`)

## Problem Statement

The validator-baseline repair plan was complete but lacked a same-feature ADR and research edge, so VaultSpec could not distinguish the completed repair from an orphaned plan.

## Considerations

This ADR is a curation authority alignment record. It does not approve a new registry module boundary, raise reviewability baselines, or change validator behavior.

## Constraints

The closeout is vault-only. Source changes already present in the shared worktree are not modified by this curation pass.

## Implementation

Treat the linked research record and plan as the authority chain for the completed validator-baseline repair. The row-width-pressure blocker remains the upstream context for why the repair existed.

## Rationale

A local ADR prevents future agents from interpreting the repair plan as ungrounded work while keeping the decision narrow and historical.

## Consequences

VaultSpec plan and schema checks can resolve the validator-baseline repair authority path. Future registry reviewability changes still require their own decision records.

## Codification candidates

No project rule is promoted from this curation ADR.
