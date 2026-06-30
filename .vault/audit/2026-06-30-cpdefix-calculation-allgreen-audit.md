---
tags:
  - '#audit'
  - '#cpdefix-calculation-allgreen'
date: '2026-06-30'
modified: '2026-06-30'
related: []
---

# `cpdefix-calculation-allgreen` audit: focused calculation checkpoint

## Scope

This checkpoint records the calculation-adjacent verification slices run during
the 2026-06-30 current-profile and legal-grounding cleanup campaign. It covers
focused tests only: Modelo 130 casilla-05 carry, IVA compensation relation
prefill, IVA compensation filed-observation history, and declaration parser
chain splits touched during the campaign.

It is not a full-tree all-green certification. No full `pytest`, full registry
gate, or full Vaultspec gate was run for this checkpoint.

## Findings

### focused-gates | low | calculation slices passed their focused gates

The focused calculation slices passed their local gates:
`test_modelo_130_casilla_05_carry.py` passed 5 unit tests,
`test_iva_compensation_relation_prefill.py` and
`test_iva_compensation_filed_observations.py` passed 13 unit tests together,
and the declaration M303 parser/historical split passed its focused unit tests.
These gates prove the edited slices remain behaviourally intact after
current-profile fixture cleanup and test-file splitting.

### allgreen-scope | medium | full calculation all-green remains unclaimed

The file name reflects the intended checkpoint topic, but the evidence gathered
in this run is focused, not global. Treat this audit as a slice-level status
record until a full calculation/registry gate is run and recorded separately.

## Recommendations

Run and record a full calculation gate before marking any broader
`cpdefix-calculation-allgreen` campaign objective complete. If unrelated
pre-existing failures remain, classify them by owner and surface them as
explicit non-closure evidence rather than calling the tree green.
