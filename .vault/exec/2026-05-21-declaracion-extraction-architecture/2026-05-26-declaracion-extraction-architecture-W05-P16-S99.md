---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P16.S99'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-22-declaracion-extraction-architecture-w04-p08-s86-w04-p09-s27-w04-p10-s29-w05-p11-s37-s95-exec]]'
---

# W05.P16.S99 - historical pre-2025 Modelo 037 decision

Closed the decision: do not open a historical pre-2025 Modelo 037
registry/profile slice inside the current declaration-extraction rollout.

## Legal grounding

BOE-A-2025-410 suppresses Modelo 037 and explains that the simplified
census path is now offered through Modelo 036. The same order modifies
Orden EHA/1274/2007 by removing the Modelo 037-specific articles and
annex. The consolidated BOE text for Orden EHA/1274/2007 reflects that
current legal state.

## Decision

The current product surface is current-law declaration extraction.
Historical Modelo 037 support would require a separate historical-slice
ADR/plan with explicit pre-2025 effective dates, BOE/AEAT source scope,
and an authorised historical fixture. It should not block or broaden the
current `declaracion-extraction-architecture` rollout.

## Sources checked

- https://www.boe.es/buscar/doc.php?id=BOE-A-2025-410
- https://www.boe.es/buscar/act.php?id=BOE-A-2007-9508
