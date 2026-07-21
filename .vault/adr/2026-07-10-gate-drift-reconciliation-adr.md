---
tags:
  - '#adr'
  - '#gate-drift-reconciliation'
date: '2026-07-10'
modified: '2026-07-13'
related:
  - "[[2026-07-10-gate-drift-reconciliation-research]]"
  - "[[2026-07-08-gate-drift-reconciliation-plan]]"
  - "[[2026-07-08-gate-drift-reconciliation-audit]]"
---
# gate-drift-reconciliation adr: retrospective reconciliation closeout | (**status:** `accepted`)

## Problem Statement

The gate-drift reconciliation plan closed after resolving health-check residue that no active campaign owned. At execution time, an operator-directed no-ADR posture meant the usual ADR-to-plan-to-execution lineage was unavailable. The historical audit therefore carries the available closure evidence.

## Considerations

The completed feature includes a boundary correction, refusal-order reconciliation, fixture and documentation repairs, and hygiene remediation. Existing authority remains the authority for decisions it already governs. The historical absence of an ADR must remain visible rather than be presented as prior approval.

## Considered options

- Retrospective closeout ADR (chosen): records the completed evidence chain without claiming pre-approval or creating a new product decision.
- Validator exception (rejected): would hide a real authority-graph gap and leave the completed plan without ADR lineage.
- Archive or feature reclassification (rejected): would obscure a distinct completed campaign and weaken traceability.

## Constraints

This record is limited to retrospective governance closure. It does not independently approve past implementation, widen any earlier architectural or product decision, or justify backfilling execution records without step-level proof.

## Implementation

Accept this ADR as the governance record for the completed feature. The plan may link to this ADR and the feature index may represent the completed evidence chain. Existing audit evidence remains the execution record unless an individual step can later be reconstructed with precise, verifiable proof.

## Rationale

A feature-specific closeout repairs the missing authority edge while preserving the historical caveat. It is narrower and more truthful than a validator exception, an archive, or a new implementation decision.

## Consequences

Future architectural work must receive ADR approval before execution. Per-step execution records must not be created merely to improve status display; each requires truthful evidence.
