---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:6109cd04aa730c28c7d630e89bc3b5b3c4639ef2fea4d5496967339d123a4c0c'
step_id: 'S33'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Give the module ratchet a verifiable disposition for capability a production contract requires but no entrypoint reaches: the classification ledger had already adjudicated domain.contabilidad and domain.is_compensation as staged capability, but the intentional kind enum held only design_time_authority, so the sole way to record them was widening allowed; add declared_by_contract, which must name the declaring file and is refused on load when that file stops naming the module, and close the hole the shared enum opened in the symbol ratchet where no declared_by exists to check

## Scope

- `dev/quality/unreachable_module_ratchet.py`

## Changes

- `M` `dev/quality/unreachable_module_ratchet.py`
- `M` `dev/quality/unreachable_module_ratchet.toml`
- `M` `dev/quality/unused_symbol_ratchet.py`
- `A` `dev/quality/tests/test_declared_by_contract_dispositions.py`
- `verify:` `uv run --no-sync pytest dev/quality/tests dev/audit/tests -q` -> `pass`

## Notes

The module ratchet still reports `cadrumo.application.ledger.import_preparation`.
It is deliberately left red rather than dispositioned: its only declarer is the
dev capability matrix, and the TUI import door that would consume it can never
open, so a `declared_by_contract` entry would quiet a module whose contract is
itself unsatisfiable. That decision remains `W05.P12.S28`.
