---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:657f51224a12dc32fc5dc5c5ff826b07c25328bb633850a77127e0ea89fa6fb2'
step_id: 'S38'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Test the generator emits a schema-shaped marketplace tree whose plugins[] entry resolves to the emitted plugin

## Scope

- `src/aeat/agent/tests/test_marketplace_generation.py`

## Description

- Add `test_marketplace_generation.py`: the emitted manifest is schema-shaped and its `plugins[]` source resolves to the plugin materialised in the same call; the served plugin is byte-identical to a standalone `materialise_plugin` emission (no drift by construction); the checked-in `packaging/marketplace` scaffold equals the generator output (scaffold-lock); and where the `claude` CLI is on PATH the emitted marketplace passes `claude plugin validate --strict` as an additional gate (structural assertions always run).
- Commit `4da3a62c05`. 4 passed; ruff clean.

## Outcome

- Marketplace/plugin/scaffold coherence is gate-enforced, including against the live validator.

## Notes

Authored inline by the coordinator (the original executor died at the rate limit before starting this step). Includes one beyond-plan assertion — the scaffold-lock test — so a hand-edit to `packaging/marketplace/.claude-plugin/marketplace.json` that diverges from the generator fails CI.
