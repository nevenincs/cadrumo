---
tags:
  - "#exec"
  - "#self-healing-sync"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-self-healing-sync-plan]]"
  - "[[2026-04-12-self-healing-sync-adr]]"
---

# step 3 — strategies + dispatcher with bounded policy

- `_strategies/_base.py` — `HealingStrategy` ABC,
  `StrategyAction` / `StrategyOutcome` (frozen strict pydantic v2).
- `_strategies/_additive_allowlist.py` — bounded auto-heal gated on
  classification ∈ ADDITIVE AND kind ∈ allowlist, with the auto_heal
  flag checked first.
- `_strategies/_escalate.py` — fallback strategy that always emits
  PENDING.
- `_strategies/_benign.py` — records BENIGN divergences for audit.
- `_dispatcher.py` — `HealingDispatcher` + `HealingPlan`. Includes a
  second-line `_enforce_bounded_policy` guard that downgrades any
  erroneous AUTO_HEALED outcome for a non-ADDITIVE or
  non-allowlisted record to ESCALATED with WARN logging.
- `test_strategies.py` — per-strategy happy + refusal paths.
- `test_bounded_policy.py` — the critical invariant test, parametrised
  across every `DivergenceKind` under both empty and full allowlist
  configurations.

44 unit tests green.
