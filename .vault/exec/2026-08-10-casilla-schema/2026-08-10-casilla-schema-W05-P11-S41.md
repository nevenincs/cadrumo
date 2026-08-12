---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:ff5d791f5c26bfb51a6ba9b4719e9d11d149558c81d2345de5e1bedcdb723e6a'
step_id: 'S41'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# correct the standing collect gate to measure the full repository

## Scope

- `.vault/plan/2026-08-10-casilla-schema-plan.md`

## Description

- Ground the collect-only behavior in the project pytest configuration and the prior full-collection audit.
- Replace the ambiguous bare collect command with an explicit serial full-tree collection that clears inherited `addopts`.
- Execute the corrected command twice against the current tree.

## Outcome

The plan's global gate now names `uv run --no-sync pytest --collect-only -q -n 0 --override-ini=addopts=` and states why the empty override is load-bearing. The gate therefore measures all marker cohorts instead of silently inheriting the project default unit-lane selection.

## Verification

- Mandatory code RAG: `uv run --no-sync vaultspec-rag search "pytest collect-only inherits addopts marker deselect rule named collection gate casilla schema" --type code --port 8766 --timeout 120` passed and ranked the real marker-selection reachability evidence.
- Mandatory Vault RAG: `uv run --no-sync vaultspec-rag search "casilla schema standing collect gate unit lane full collection plan verification" --type vault --port 8766 --timeout 120` passed and ranked the S01 audit's established full-collection command plus this plan.
- First exact full serial collection exited zero in 100.5 seconds.
- Second exact full serial collection exited zero with `29087 tests collected in 70.10s`.
- The plan body update was performed only through `vaultspec-core vault set-body`, preserving its two non-schema prose blocks.

## Notes

The initial combined plan-update and exec-scaffold command timed out after 34 seconds while VaultSpec continued its own work. Read-only inspection confirmed both requested writes had completed successfully before any retry, so neither mutation was repeated.
