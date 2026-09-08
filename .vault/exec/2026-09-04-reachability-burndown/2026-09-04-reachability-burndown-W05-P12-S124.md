---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:3467e497199a2fe8e99f63ae2e3e798f90d1ea940ccdc36592bd0a7696baf315'
step_id: 'S124'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---
# Replace the unreachable-module, unused-symbol, and unconsumed-export identity baselines and every frozen or intentional disposition with live zero-target reports, so reachability gates derive their entire finding set from the current tree

## Scope

- `dev/quality/unreachable_module_ratchet.toml`

## Changes

- `D` `dev/quality/unreachable_module_ratchet.toml`
- `D` `dev/quality/unused_symbol_ratchet.toml`
- `D` `dev/quality/unconsumed_export_ratchet.toml`
- `D` `dev/quality/unreachable_module_ratchet.py`
- `D` `dev/quality/unused_symbol_ratchet.py`
- `D` `dev/quality/unconsumed_export_ratchet.py`
- `A` `dev/quality/unreachable_module_coverage.py`
- `A` `dev/quality/unused_symbol_coverage.py`
- `A` `dev/quality/unconsumed_export_coverage.py`
- `D` baseline- and disposition-specific tests under `dev/tests/` and `dev/quality/tests/`
- `A` zero-target detector-teeth tests for all three live projections under `dev/quality/tests/`
- `M` `justfile`, `dev/quality/suite.py`, and `.github/workflows/ci.yml` to invoke the replacement gates without legacy aliases
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md` to make the signal-burndown cadence and development-state boundary durable
- `grounding:` semantic RAG surfaced accepted `2026-09-07-quality-gate-zero-closure-blind-green-gates-adr`; the replacements follow its exact-zero, real-tree, positive-control, and no-baseline constraints
- `verify:` focused detector and gate-table tests -> `17 passed`
- `verify:` focused Python lint -> `all checks passed`
- `verify:` `just check-unreachable-module-coverage` -> expected red, `50` live module findings
- `verify:` `just check-unused-symbol-coverage` -> expected red, `385` exact symbol findings and `21` orphaned test modules
- `verify:` `just check-unconsumed-export-coverage` -> expected red, `275` live export findings

## Notes

The former green results depended on identity snapshots, a frozen TUI namespace,
per-symbol intentional keeps, and module dispositions. All are deleted. The new gates
derive and print complete current finding sets and have no input through which a module,
symbol, test, or export can be assigned development status. Red is the honest standing
state until each finding is resolved through its product or development boundary owner.
