---
tags:
  - '#exec'
  - '#core-authority'
step_id: S87
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W10.P26.S87 - BLOCKED: _normalise_period functions are domain-divergent

## Outcome

BLOCKED. The two `_normalise_period` functions are domain-divergent intentional pairs
with different contracts; consolidation is incorrect.

- `application/filing/_import.py:143` — signature: `(*, modelo, ejercicio, raw_period,
  schema_provider)`. Complex canonicalisation: quarterly tokens become "YYYYQ1..4",
  monthly become "YYYY-MM", annual become "YYYYA". Uses `RegistryImportSchemaProvider`.

- `application/filing/reconciliation/_reconcile.py:329` — signature:
  `(period, *, ejercicio=None, supported_periods)`. Simpler: strip/lowercase a period
  label for tolerant comparison against a set of known periods.

These are not the same transformation. The semantic audit (PAIR F-03) described them
as "same name, same transformation" based on name similarity alone; reading the bodies
reveals they serve different concerns (import canonicalisation vs reconciliation matching).

Per the W04/W05 lesson: verify domain reality before collapsing duplicates.

## Files touched

None — no code changes.

## Verification

N/A (no change).
