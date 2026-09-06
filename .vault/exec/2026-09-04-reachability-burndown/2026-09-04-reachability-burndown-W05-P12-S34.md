---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:cf81faf2936993a50d210363617acbaa4242c48b7f4b0781b9ac1bd4c5cc44bf'
step_id: 'S34'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Repair the classification ledger's own drift, which had gone red on two gates: three clusters filed a symbol under an area the audit never names, so the staleness check read a live finding as one the audit had stopped reporting; the three PublicResultV1 models had genuinely stopped being reported because the dead projectors beside them construct them and a construction counts as a use even when the constructor is unreached; and the reported module import_preparation carried no entry at all, which the ledger requires and the earlier reading had wrongly ruled out; also adjudicate the process-cache reset seams as test-support after checking their docstrings' production claims against the closed override_settings field list

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py -m ""` -> `pass`
