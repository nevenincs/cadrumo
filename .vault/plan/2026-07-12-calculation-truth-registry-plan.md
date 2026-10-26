---
tags:
  - '#plan'
  - '#calculation-truth-registry'
date: '2026-07-12'
modified: '2026-08-25'
body_hash: 'sha256:95e42849893eeff919146516dda85fcbbeffaf6af7659e3b8437e69c8037ec5e'
tier: L2
related:
  - '[[2026-07-12-calculation-truth-registry-audit]]'
  - '[[2026-07-12-calculation-truth-registry-reference]]'
  - '[[2026-07-14-calculation-export-import-adjudication-adr]]'
---

# `calculation-truth-registry` `legacy-backlog reconciliation` plan

### Phase `P01` - evidence-backed legacy classification

Turn the legacy checklist into a current, source-grounded disposition ledger before any further registry implementation is scheduled.

- [x] `P01.S01` - Classify each legacy unchecked item against current source, accepted decisions, and recorded execution evidence; `.vault/plan/, .vault/exec/, .vault/audit/, .vault/research/`.
- [x] `P01.S02` - Publish the disposition ledger distinguishing delivered, superseded, blocked, and genuinely actionable registry work; `.vault/audit/`.

### Phase `P02` - current execution backlog

Convert only the genuinely actionable ledger entries into a separately approved implementation plan with precise ownership and verification.

- [x] `P02.S03` - Write the canonical registry implementation backlog from the classified residual ledger; `.vault/plan/`.

## Description

Create a trustworthy execution handoff for the historical calculation-registry
rebuild backlog. The accepted registry ADR remains the governing decision, but
the prior 705-item checklist cannot report executable progress. This plan
classifies that legacy material against current source and recorded evidence,
then writes a separately approvable implementation backlog containing only
work that still exists. It does not implement or close any registry code row
by inference.

## Operating boundary

The disposition ledger is evidence, not a substitute for legal or executable
verification. A row is delivered only when source and execution evidence agree;
it is superseded only when a later accepted decision displaces it; and it stays
open when neither conclusion is defensible.
## Parallelization

`P01.S01` precedes `P01.S02`, because the ledger must contain the source and
Vault evidence before it can publish a disposition. `P02.S03` follows both
classification steps. No registry implementation is scheduled in parallel with
this planning reconciliation.

## Verification

The plan is complete only when every legacy unchecked item has exactly one
evidence-backed disposition, the published ledger exposes all genuinely open
items and their blockers, and the successor implementation plan contains only
canonical steps grounded in the accepted registry ADR. The feature-scoped Vault
checks and feature index must be clean.
