---
tags:
  - '#adr'
  - '#integration-fixture-drift'
date: '2026-07-10'
modified: '2026-07-13'
related:
  - "[[2026-07-10-integration-fixture-drift-research]]"
  - "[[2026-07-08-integration-fixture-drift-plan]]"
  - "[[2026-07-08-integration-fixture-drift-audit]]"
---
# integration-fixture-drift adr: retrospective fixture recovery closeout | (**status:** `accepted`)

## Problem Statement

The integration-fixture-drift plan closed after repairing tests that had fallen behind changed identity, session, and behavioural contracts. It executed without a feature-specific ADR and therefore lacks the normal ADR-backed execution lineage.

## Considerations

The work aligns fixtures to live contracts. It does not itself decide application behavior or architecture. Product-behaviour and architectural outcomes remain governed by prior authority or explicit operator rulings.

## Considered options

- Retrospective closeout ADR (chosen): documents the completed evidence, scope, and authority boundaries without claiming pre-approval.
- Validator exception (rejected): would silence a genuine missing authority edge without restoring traceability.
- Merge into the gate-drift feature (rejected): would conflate a distinct fixture-recovery campaign with its broader health-check predecessor.

## Constraints

The accepted scope is contract-aligned fixture repair and documented triage of residual failures. Confirmed flakes, peer-owned failures, and unresolved work remain outside the closure. This ADR creates no new product or architectural direction.

## Implementation

Accept this ADR as the retrospective governance record for the completed fixture-recovery feature. The plan may link to this ADR and the feature index may represent the completed documentation chain. Historical audit evidence remains authoritative for execution until individual steps can be reconstructed with precise proof.

## Rationale

A feature-specific closeout preserves the campaign's distinct evidence trail and restores the Vault authority graph without manufacturing decisions that the work did not make.

## Consequences

Future product or architectural work requires ordinary ADR approval before execution. Execution records may be added only when their step-level evidence is complete.
