---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:24abd64036a0ed176c09445af7125cfd36baba1af75c9145018438c1b81f4035'
step_id: 'S83'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Re-test the portal-drift entry and fix the defect that is actually there: the ledger claimed the missing wiring was passing drift events into the health probe, but no shipped module reads the portal registry except that row, which only counts entries, so nothing navigates to a registered URL and nothing can observe the value the drift evaluator compares against; the events are unobservable rather than un-passed and the remedy is a live-read surface, which is capability. What was a real defect is the row asserting a bare zero drift count it has never measured, so report whether the axis was evaluated at all.

## Scope

- `src/cadrumo/application/preflight.py`
- `src/cadrumo/application/tests/test_preflight.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/application/preflight.py`
- `M` `src/cadrumo/application/tests/test_preflight.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `pytest .../test_preflight.py` 23 passed, 4 of them the portal rows
- `verify:` module ratchet, secure-store gate and docstring ratchet exit 0;
  duplication 10 / 0.05%; dead code 0; unused 1040, exact 411
- `verify:` symbol ratchet still exits 1 on the same two peer-introduced lines,
  unchanged and deliberately unabsorbed
- `verify:` `ruff check` and `ty check` clean

## Notes

The ledger entry was wrong about where the defect was, and asking how the live
path achieves the thing the symbol names is what settled it. Nothing in the
shipped tree reads `PORTAL_REGISTRY` except the health row itself, which counts
its entries; no adapter navigates to a registered URL. So the drift events are
not un-passed, they are unobservable, and the module docstring already says the
observation is produced elsewhere under a live-read access gate that does not
exist yet. Staged capability, not missing wiring.

The real defect was one line away from the claimed one. The row reported
`drift_count: 0` with nothing beside it, which asserts a zero the product has
never measured -- the absent-versus-zero collapse this codebase refuses
everywhere else. It now reports `drift_evaluated: False` too. Severity stays
`OK`, because the question this check owns is whether the registry assembled,
and it did.

The control is what keeps the disclaimer honest rather than permanent: with an
observation supplied the flag must flip to True. Hard-coding False would
otherwise satisfy the offline case forever.
