---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S310'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P13.S310`

Added `CAST-RATIONALE-LEDGER-RULE-REPO-INJECT` markers at the two `cast(LedgerClassificationRuleRepository, rule_repository)` sites in `_actions.py`.

- Modified: `src/aeat/application/ledger/_actions.py`

## Description

Both cast sites use an `object | None` injection-friendly parameter type to allow test injection without widening the public API. The markers are placed as inline comments immediately above the `cast(` expression inside the parenthesised ternary block, which is the only placement the backward-scan heuristic in the inventory test can reach (a code line intervenes between the outer assignment and the cast itself).

## Tests

`src/aeat/test_cast_rationale_inventory.py` confirms both sites carry their markers.
